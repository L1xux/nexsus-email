import base64
import json
import re
from typing import Optional

from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.category import Category

settings = get_settings()


class ThreadClassificationResult(BaseModel):
    status: str
    confidence: float
    reason: str


SYSTEM_PROMPT = """You are an email thread classification assistant. Your task is to classify an entire email conversation thread into one of three statuses based on whether the user needs to take action.

CLASSIFICATION CRITERIA:

1. "ToDo" - User needs to take action:
   - The thread contains a request or task assigned to the user
   - Contains questions directed at the user that require response
   - Action items, deadlines, or assignments are mentioned
   - Requires a response or follow-up from the user

2. "Waiting" - User is waiting for someone else:
   - User has previously sent a message and is awaiting a reply
   - Thread shows the user expecting a response from another party
   - Contains confirmation requests where someone is waiting on user

3. "Done" - No action needed:
   - Purely informational threads (newsletters, announcements)
   - Automated notifications, system alerts
   - User has completed the task and thread is closed
   - Social notifications, marketing emails

IMPORTANT GUIDELINES:
- Consider the ENTIRE conversation history in the thread
- The latest message may not be the most important one
- If the user has already responded to a request, consider if the thread is now waiting for reply
- When in doubt, classify as "ToDo" (action required)
- Auto-generated emails are usually "Done"
- Emails with clear action verbs (please, could you, would you, need to, must) are "ToDo"

OUTPUT FORMAT:
You MUST respond with valid JSON only, no other text. Use this exact schema:
{"status": "ToDo|Waiting|Done", "confidence": 0.0-1.0, "reason": "Brief explanation in 5-20 words"}

Example outputs:
{"status": "ToDo", "confidence": 0.95, "reason": "Client requested quote, awaiting response"}
{"status": "Waiting", "confidence": 0.88, "reason": "User sent proposal, waiting for client reply"}
{"status": "Done", "confidence": 0.92, "reason": "Newsletter with no action required"}
"""


def _extract_email_from_sender(sender: str) -> Optional[str]:
    match = re.search(r"<(.+?)>", sender)
    return match.group(1) if match else sender


def _decode_body(payload_body: Optional[dict]) -> Optional[str]:
    if not payload_body:
        return None
    data = payload_body.get("data")
    if not data:
        return None
    return base64.urlsafe_b64decode(data).decode("utf-8")


def _parse_message_headers(message: dict) -> dict:
    headers = message.get("payload", {}).get("headers", [])
    header_dict = {h["name"].lower(): h["value"] for h in headers}
    
    sender = header_dict.get("from", "")
    sender_email = _extract_email_from_sender(sender) if sender else None
    
    payload = message.get("payload", {})
    body_text = _decode_body(payload.get("body"))
    
    if not body_text:
        for part in payload.get("parts", []):
            if part.get("mimeType") == "text/plain":
                body_text = _decode_body(part.get("body"))
                if body_text:
                    break
    
    return {
        "subject": header_dict.get("subject", ""),
        "sender": sender,
        "sender_email": sender_email,
        "snippet": message.get("snippet", ""),
        "body_text": body_text or "",
    }


def _build_conversation_context(messages: list[dict]) -> str:
    context_parts = []
    for idx, msg in enumerate(messages):
        parsed = _parse_message_headers(msg)
        context_parts.append(
            f"Message {idx + 1}:\n"
            f"From: {parsed['sender']}\n"
            f"Subject: {parsed['subject']}\n"
            f"Snippet: {parsed['snippet'][:200] if parsed['snippet'] else ''}\n"
            f"Body: {parsed['body_text'][:500] if parsed['body_text'] else '(No body)'}\n"
        )
    return "\n".join(context_parts)


async def classify_thread(
    thread_subject: str,
    thread_messages: list[dict],
    user_id: int,
    db: AsyncSession,
) -> ThreadClassificationResult:
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    
    conversation_context = _build_conversation_context(thread_messages)
    
    user_content = f"""Classify this email thread:

Thread Subject: {thread_subject}

Conversation History:
{'='*50}
{conversation_context}
{'='*50}

Analyze the entire conversation and determine the current status of this thread."""

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=300,
        )
        
        result = json.loads(response.choices[0].message.content.strip())
        
        status = result.get("status", "ToDo")
        if status not in ["ToDo", "Waiting", "Done"]:
            status = "ToDo"
        
        confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
        reason = result.get("reason", "Classification completed")
        
        return ThreadClassificationResult(
            status=status,
            confidence=confidence,
            reason=reason
        )
        
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"Thread classification error: {e}")
        return ThreadClassificationResult(
            status="ToDo",
            confidence=0.3,
            reason="Failed to parse response, defaulting to ToDo"
        )
    except Exception as e:
        print(f"Thread classification error: {e}")
        return ThreadClassificationResult(
            status="ToDo",
            confidence=0.3,
            reason=f"Classification failed: {str(e)[:20]}"
        )


async def classify_thread_category(
    thread_subject: str,
    thread_messages: list[dict],
    user_id: int,
    db: AsyncSession,
) -> tuple[str, float]:
    CATEGORY_PROMPT = """You are an email category classifier. Classify email threads into one of these categories:

- Primary: Important emails from people you know, work colleagues, or emails requiring your attention
- Social: Social media notifications (Facebook, Twitter, LinkedIn, Instagram, etc.)
- Promotions: Marketing emails, deals, discounts, promotional content from companies
- Updates: Newsletters, news digests, product updates, software release notes
- Personal: Personal correspondence from family, friends

Consider the ENTIRE conversation thread when classifying.

Respond with JSON only:
{"category": "CategoryName", "confidence": 0.0-1.0}

Example: {"category": "Primary", "confidence": 0.92}"""
    
    category_result = await db.execute(
        select(Category).where(
            Category.user_id == user_id,
            Category.is_active == True
        )
    )
    categories = category_result.scalars().all()
    
    if not thread_messages:
        return "Primary", 0.3
    
    first_parsed = _parse_message_headers(thread_messages[0])
    last_parsed = _parse_message_headers(thread_messages[-1])
    
    user_content = f"""Thread Subject: {thread_subject}

First Message:
From: {first_parsed['sender']}
Body: {first_parsed['body_text'][:500] if first_parsed['body_text'] else 'No body'}

Latest Message:
From: {last_parsed['sender']}
Body: {last_parsed['body_text'][:500] if last_parsed['body_text'] else 'No body'}"""

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": CATEGORY_PROMPT},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=100,
        )
        
        result = json.loads(response.choices[0].message.content.strip())
        
        category = result.get("category", "Primary")
        confidence = float(result.get("confidence", 0.5))
        
        for cat in categories:
            if cat.name.lower() == category.lower():
                return cat.name, confidence
        
        return category, confidence
        
    except Exception as e:
        print(f"Thread category classification error: {e}")
        return "Primary", 0.3


async def classify_thread_with_category(
    thread_subject: str,
    thread_messages: list[dict],
    user_id: int,
    db: AsyncSession,
) -> tuple[ThreadClassificationResult, Optional[int]]:
    classification = await classify_thread(thread_subject, thread_messages, user_id, db)
    
    category_name, category_confidence = await classify_thread_category(
        thread_subject, thread_messages, user_id, db
    )
    
    category_result = await db.execute(
        select(Category).where(
            Category.user_id == user_id,
            Category.name == category_name,
        )
    )
    category = category_result.scalar_one_or_none()
    category_id = category.id if category else None
    
    return classification, category_id
