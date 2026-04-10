import json
from typing import Optional
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.config import get_settings
from app.models.category import Category
from app.models.email import EmailStatus
from app.services.rag import retrieve_similar_examples, format_rag_examples

settings = get_settings()


class ClassificationResult(BaseModel):
    status: str
    confidence: float
    reason: str


SYSTEM_PROMPT = """You are an email classification assistant. Your task is to classify incoming emails into one of three statuses based on whether the user needs to take action.

CLASSIFICATION CRITERIA:

1. "ToDo" - User needs to take action:
   - Email asks the user to do something (reply, click a link, complete a task)
   - Contains requests, assignments, or deadlines
   - Requires a response or follow-up
   - Contains questions directed at the user
   - Action items, todo items, or tasks are mentioned

2. "Waiting" - User is waiting for someone else:
   - User has sent a previous email and is awaiting a reply
   - Contains phrases like "waiting for", "pending", "awaiting"
   - Thread shows the user is expecting a response
   - Contains confirmation requests from others

3. "Done" - No action needed:
   - Purely informational emails (newsletters, announcements)
   - automated notifications, system alerts
   - Read-only updates that don't require response
   - Completed tasks or resolved issues
   - Social notifications, marketing emails

IMPORTANT GUIDELINES:
- Be strict in classification - when in doubt, classify as "ToDo" (action required)
- If the email is a reply to something the user sent, consider if they are waiting for a response
- Auto-generated emails are usually "Done"
- Emails with clear action verbs (please, could you, would you, need to, must) are "ToDo"

OUTPUT FORMAT:
You MUST respond with valid JSON only, no other text. Use this exact schema:
{"status": "ToDo|Waiting|Done", "confidence": 0.0-1.0, "reason": "Brief explanation in 5-15 words"}

Example outputs:
{"status": "ToDo", "confidence": 0.95, "reason": "Contains explicit request to review document by Friday"}
{"status": "Waiting", "confidence": 0.88, "reason": "Following up on previous sent email, awaiting reply"}
{"status": "Done", "confidence": 0.92, "reason": "Automated newsletter with no action required"}
"""


async def classify_email(
    subject: str,
    sender: str,
    body: str,
    user_id: int,
    db: AsyncSession,
) -> ClassificationResult:
    """
    Classify an email into ToDo/Waiting/Done status using GPT-4o-mini with RAG enhancement.
    
    Args:
        subject: Email subject line
        sender: Email sender (full format)
        body: Email body text
        user_id: User ID for context
        db: Database session
    
    Returns:
        ClassificationResult with status, confidence, and reason
    """
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    
    # Combine text for RAG lookup
    text_for_rag = f"From: {sender}\nSubject: {subject}\n{body[:500] if body else ''}"
    
    # Retrieve similar past examples from Qdrant
    similar_examples = await retrieve_similar_examples(
        text_to_embed=text_for_rag,
        user_id=user_id,
        top_k=3,
    )
    
    # Format RAG examples for few-shot learning
    rag_context = format_rag_examples(similar_examples)
    
    # Build the system prompt with RAG context if available
    system_prompt = SYSTEM_PROMPT
    if rag_context:
        system_prompt = SYSTEM_PROMPT + rag_context + "\n\nUse these examples to inform your classification decision."
    
    user_content = f"""Please classify this email:

From: {sender}
Subject: {subject}

Body:
{body[:2000] if body else '(No body content)'}"""

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=200,
        )
        
        result_text = response.choices[0].message.content.strip()
        
        result = json.loads(result_text)
        
        status = result.get("status", "ToDo")
        if status not in ["ToDo", "Waiting", "Done"]:
            status = "ToDo"
        
        confidence = float(result.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))
        
        reason = result.get("reason", "Classification completed")
        
        # Add RAG enhancement info if examples were used
        if similar_examples:
            reason = f"{reason} (RAG: {len(similar_examples)} similar examples)"
        
        return ClassificationResult(
            status=status,
            confidence=confidence,
            reason=reason
        )
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        return ClassificationResult(
            status="ToDo",
            confidence=0.3,
            reason="Failed to parse response, defaulting to ToDo"
        )
    except Exception as e:
        print(f"Classification error: {e}")
        return ClassificationResult(
            status="ToDo",
            confidence=0.3,
            reason=f"Classification failed: {str(e)[:20]}"
        )


async def classify_email_with_category(
    subject: str,
    sender: str,
    body: str,
    user_id: int,
    db: AsyncSession,
) -> tuple[ClassificationResult, Optional[int]]:
    """
    Classify email for both status AND category.
    
    Returns:
        Tuple of (ClassificationResult, category_id)
    """
    # Get status classification (with RAG)
    classification = await classify_email(subject, sender, body, user_id, db)
    
    # Get category classification
    category_result = await classify_category(subject, sender, body, user_id, db)
    category_name, category_confidence = category_result
    
    # Find or return category ID
    cat_result = await db.execute(
        select(Category).where(
            Category.user_id == user_id,
            Category.name == category_name,
        )
    )
    category = cat_result.scalar_one_or_none()
    category_id = category.id if category else None
    
    return classification, category_id


async def classify_category(
    subject: str,
    sender: str,
    body: str,
    user_id: int,
    db: AsyncSession,
) -> tuple[str, float]:
    """
    Classify email into a category (Primary, Social, Promotions, Updates, Personal).
    """
    CATEGORY_PROMPT = """You are an email category classifier. Classify emails into one of these categories:

- Primary: Important emails from people you know, work colleagues, or emails requiring your attention
- Social: Social media notifications (Facebook, Twitter, LinkedIn, Instagram, etc.)
- Promotions: Marketing emails, deals, discounts, promotional content from companies
- Updates: Newsletters, news digests, product updates, software release notes
- Personal: Personal correspondence from family, friends

Respond with JSON only:
{"category": "CategoryName", "confidence": 0.0-1.0}

Example: {"category": "Primary", "confidence": 0.92}"""

    result = await db.execute(
        select(Category).where(
            Category.user_id == user_id,
            Category.is_active == True
        )
    )
    categories = result.scalars().all()
    
    category_names = [c.name for c in categories] if categories else ["Primary", "Social", "Promotions", "Updates", "Personal"]
    
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    
    user_content = f"""Subject: {subject}
From: {sender}
Body: {body[:1000] if body else 'No body'}"""

    try:
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
        
        result_text = response.choices[0].message.content.strip()
        result = json.loads(result_text)
        
        category = result.get("category", "Primary")
        confidence = float(result.get("confidence", 0.5))
        
        for cat in categories:
            if cat.name.lower() == category.lower():
                return cat.name, confidence
        
        return category, confidence
        
    except Exception as e:
        print(f"Category classification error: {e}")
        return "Primary", 0.3


def get_email_status_enum(status: str) -> EmailStatus:
    """Convert string status to EmailStatus enum."""
    status_map = {
        "todo": EmailStatus.TODO,
        "waiting": EmailStatus.WAITING,
        "done": EmailStatus.DONE,
        "inbox": EmailStatus.INBOX,
    }
    return status_map.get(status.lower(), EmailStatus.TODO)
