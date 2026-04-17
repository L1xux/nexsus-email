import base64
import json
import re
from datetime import datetime
from typing import Optional

from openai import AsyncOpenAI
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.category import Category

settings = get_settings()


class ThreadClassificationResult(BaseModel):
    status: str   # lowercase: "todo", "waiting", "done"
    confidence: float
    reason: str
    deadline: Optional[datetime] = None


SYSTEM_PROMPT = """You are an email thread classification assistant. Your task is to classify an email thread into one of four statuses.

IMPORTANT RULE: Only classify a thread as "todo", "waiting", or "done" if it is a BUSINESS email thread that requires active management. All non-business emails (social media, promotions, newsletters, personal, automated notifications) MUST be classified as "inbox".

CLASSIFICATION CRITERIA:

1. "inbox" - DEFAULT for ALL non-business emails (HIGHEST PRIORITY):
   - Social media notifications (Facebook, Twitter, LinkedIn, Instagram notifications)
   - Marketing emails, promotional content, discounts, deals
   - Newsletters, news digests, product updates
   - Automated system notifications (password resets, security alerts, receipt confirmations)
   - Personal emails from friends or family
   - Any email that is not clearly a business/work communication
   - If unsure whether it's business → default to "inbox"

2. "todo" - Business emails where user needs to take action:
   - Work tasks, project assignments, or requests from colleagues/clients
   - Questions directed at the user that require a business response
   - Action items with deadlines from work context
   - Contracts, invoices, or business documents needing review/approval

3. "waiting" - Business emails where user is awaiting a business reply:
   - User has sent a business message and is waiting for a response
   - Business negotiations, discussions, or conversations in progress
   - Pending confirmations from business contacts

4. "done" - Business threads that are resolved/closed:
   - Business threads where the task is completed
   - Business newsletters or work announcements with no action needed
   - Calendared meeting invites that have passed

DEADLINE EXTRACTION:
- If the thread mentions a specific deadline or due date, extract it as an ISO 8601 datetime string.
- Look for patterns like: "by Friday", "due on March 15", "deadline: 2026-03-20", "before EOD", "next Monday", etc.
- If no deadline is mentioned, set "deadline" to null.
- Only extract dates the user is expected to meet — not dates when someone else will respond.

IMPORTANT GUIDELINES:
- When in doubt between business and non-business → "inbox"
- Newsletters about products/services → "inbox"
- Auto-generated emails of any kind → "inbox"
- Work emails from colleagues/clients → "todo"/"waiting"/"done" based on context
- Any thread that doesn't clearly belong to todo/waiting/done → "inbox"

OUTPUT FORMAT:
You MUST respond with valid JSON only, no other text. Use this exact schema:
{"status": "inbox|todo|waiting|done", "confidence": 0.0-1.0, "reason": "Brief explanation in 5-20 words", "deadline": "YYYY-MM-DD or null"}

Example outputs:
{"status": "inbox", "confidence": 0.97, "reason": "Newsletter digest, no business action needed", "deadline": null}
{"status": "inbox", "confidence": 0.95, "reason": "Twitter notification, non-business email", "deadline": null}
{"status": "todo", "confidence": 0.93, "reason": "Work contract needs review and signature", "deadline": "2026-04-15"}
{"status": "waiting", "confidence": 0.87, "reason": "Business proposal sent, awaiting client reply", "deadline": null}
{"status": "done", "confidence": 0.91, "reason": "Completed project signoff, no further action", "deadline": null}
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


def _parse_deadline(value) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip().lower() in ("null", "none", ""):
        return None
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d")
    except ValueError:
        try:
            return datetime.strptime(str(value).strip(), "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return None


def _normalize_status(raw: str) -> str:
    mapping = {
        "inbox": "inbox",
        "todo": "todo",
        "waiting": "waiting",
        "done": "done",
    }
    return mapping.get(raw.strip().lower(), "inbox")


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

        raw_status = result.get("status", "todo")
        status = _normalize_status(raw_status)
        confidence = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
        reason = result.get("reason", "Classification completed")
        deadline = _parse_deadline(result.get("deadline"))

        return ThreadClassificationResult(
            status=status,
            confidence=confidence,
            reason=reason,
            deadline=deadline,
        )
        
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"Thread classification error: {e}")
        return ThreadClassificationResult(
            status="inbox",
            confidence=0.3,
            reason="Failed to parse response, defaulting to inbox",
            deadline=None,
        )
    except Exception as e:
        print(f"Thread classification error: {e}")
        return ThreadClassificationResult(
            status="inbox",
            confidence=0.3,
            reason=f"Classification failed: {str(e)[:20]}",
            deadline=None,
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
