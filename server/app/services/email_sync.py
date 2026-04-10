from datetime import datetime
from typing import Optional

from google.oauth2.credentials import Credentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email import Email
from app.models.thread import EmailThread, ThreadStatus
from app.models.user import User
from app.services.gmail_service import fetch_recent_emails, parse_gmail_message
from app.services.thread_classifier import classify_thread_with_category
from app.core.google import get_thread


async def _get_or_create_thread(
    user_id: int,
    gmail_thread_id: str,
    thread_subject: Optional[str],
    thread_snippet: Optional[str],
    db: AsyncSession,
    thread_cache: dict,
) -> Optional[EmailThread]:
    if gmail_thread_id in thread_cache:
        return thread_cache[gmail_thread_id]
    
    thread_result = await db.execute(
        select(EmailThread).where(
            EmailThread.user_id == user_id,
            EmailThread.gmail_thread_id == gmail_thread_id,
        )
    )
    thread_obj = thread_result.scalar_one_or_none()
    
    if not thread_obj:
        thread_obj = EmailThread(
            user_id=user_id,
            gmail_thread_id=gmail_thread_id,
            subject=thread_subject,
            snippet=thread_snippet,
        )
        db.add(thread_obj)
        await db.flush()
    
    thread_cache[gmail_thread_id] = thread_obj
    return thread_obj


def _parse_received_at(date_string: Optional[str]) -> Optional[datetime]:
    if not date_string:
        return None
    try:
        return datetime.fromisoformat(date_string)
    except (ValueError, TypeError):
        return datetime.utcnow()


async def sync_gmail_emails(
    user_id: int,
    credentials: Credentials,
    db: AsyncSession,
    max_results: int = 50,
) -> int:
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    
    if not user:
        return 0
    
    emails_data = await fetch_recent_emails(credentials, max_results)
    
    new_count = 0
    thread_cache: dict[str, EmailThread] = {}
    
    for email_data in emails_data:
        parsed = parse_gmail_message(email_data)
        gmail_message_id = parsed["gmail_message_id"]
        gmail_thread_id = parsed.get("thread_id")
        
        existing_result = await db.execute(
            select(Email).where(
                Email.user_id == user_id,
                Email.gmail_message_id == gmail_message_id,
            )
        )
        if existing_result.scalar_one_or_none():
            continue
        
        thread_obj = None
        if gmail_thread_id:
            thread_obj = await _get_or_create_thread(
                user_id=user_id,
                gmail_thread_id=gmail_thread_id,
                thread_subject=parsed.get("subject"),
                thread_snippet=parsed.get("snippet"),
                db=db,
                thread_cache=thread_cache,
            )
        
        received_at = _parse_received_at(parsed.get("received_at"))
        
        email = Email(
            user_id=user_id,
            gmail_message_id=gmail_message_id,
            history_id=parsed.get("history_id"),
            thread_id=gmail_thread_id,
            email_thread_id=thread_obj.id if thread_obj else None,
            subject=parsed.get("subject"),
            sender=parsed.get("sender"),
            sender_email=parsed.get("sender_email"),
            recipients=parsed.get("recipients"),
            snippet=parsed.get("snippet"),
            body_text=parsed.get("body_text"),
            body_html=parsed.get("body_html"),
            label_ids=parsed.get("label_ids"),
            is_read=parsed.get("is_read", False),
            is_starred=parsed.get("is_starred", False),
            received_at=received_at,
        )
        
        db.add(email)
        new_count += 1
        
        if thread_obj:
            thread_obj.message_count += 1
            if received_at and (
                not thread_obj.last_message_at 
                or received_at > thread_obj.last_message_at
            ):
                thread_obj.last_message_at = received_at
    
    await db.commit()
    return new_count


async def classify_thread_from_gmail(
    user_id: int,
    gmail_thread_id: str,
    credentials: Credentials,
    db: AsyncSession,
) -> None:
    thread_result = await db.execute(
        select(EmailThread).where(
            EmailThread.user_id == user_id,
            EmailThread.gmail_thread_id == gmail_thread_id,
        )
    )
    thread_obj = thread_result.scalar_one_or_none()
    
    if not thread_obj:
        return
    
    gmail_thread = await get_thread(credentials, gmail_thread_id)
    messages = gmail_thread.get("messages", [])
    
    if not messages:
        return
    
    classification_result, category_id = await classify_thread_with_category(
        thread_subject=thread_obj.subject or "",
        thread_messages=messages,
        user_id=user_id,
        db=db,
    )
    
    thread_obj.status = ThreadStatus(classification_result.status.lower())
    thread_obj.classification_confidence = classification_result.confidence
    thread_obj.classification_reason = classification_result.reason
    thread_obj.category_id = category_id
    
    await db.commit()


async def sync_and_classify_thread(
    user_id: int,
    gmail_thread_id: str,
    credentials: Credentials,
    db: AsyncSession,
) -> None:
    thread_result = await db.execute(
        select(EmailThread).where(
            EmailThread.user_id == user_id,
            EmailThread.gmail_thread_id == gmail_thread_id,
        )
    )
    thread_obj = thread_result.scalar_one_or_none()
    
    if not thread_obj:
        return
    
    gmail_thread = await get_thread(credentials, gmail_thread_id)
    messages = gmail_thread.get("messages", [])
    
    new_email_count = 0
    for msg in messages:
        msg_id = msg.get("id")
        if not msg_id:
            continue
        
        existing_result = await db.execute(
            select(Email).where(
                Email.user_id == user_id,
                Email.gmail_message_id == msg_id,
            )
        )
        if existing_result.scalar_one_or_none():
            continue
        
        parsed = parse_gmail_message(msg)
        received_at = _parse_received_at(parsed.get("received_at"))
        
        email = Email(
            user_id=user_id,
            gmail_message_id=msg_id,
            history_id=msg.get("historyId"),
            thread_id=gmail_thread_id,
            email_thread_id=thread_obj.id,
            subject=parsed.get("subject"),
            sender=parsed.get("sender"),
            sender_email=parsed.get("sender_email"),
            recipients=parsed.get("recipients"),
            snippet=parsed.get("snippet"),
            body_text=parsed.get("body_text"),
            body_html=parsed.get("body_html"),
            label_ids=parsed.get("label_ids"),
            is_read=parsed.get("is_read", False),
            is_starred=parsed.get("is_starred", False),
            received_at=received_at,
        )
        
        db.add(email)
        new_email_count += 1
        
        if received_at and (
            not thread_obj.last_message_at 
            or received_at > thread_obj.last_message_at
        ):
            thread_obj.last_message_at = received_at
    
    if messages:
        thread_obj.message_count = len(messages)
        if not thread_obj.subject:
            first_msg = messages[0]
            parsed = parse_gmail_message(first_msg)
            thread_obj.subject = parsed.get("subject")
    
    if new_email_count > 0:
        classification_result, category_id = await classify_thread_with_category(
            thread_subject=thread_obj.subject or "",
            thread_messages=messages,
            user_id=user_id,
            db=db,
        )
        
        thread_obj.status = ThreadStatus(classification_result.status.lower())
        thread_obj.classification_confidence = classification_result.confidence
        thread_obj.classification_reason = classification_result.reason
        thread_obj.category_id = category_id
    
    await db.commit()


async def process_gmail_webhook(
    email_address: str,
    history_id: str,
    db: AsyncSession,
) -> None:
    user_result = await db.execute(
        select(User).where(User.email == email_address)
    )
    user = user_result.scalar_one_or_none()
    
    if not user or not user.google_access_token:
        return
    
    credentials = Credentials(
        token=user.google_access_token,
        refresh_token=user.google_refresh_token,
    )
    
    await sync_gmail_emails(user.id, credentials, db, max_results=10)
