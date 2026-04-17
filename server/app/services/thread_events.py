"""
Background AI classification for new EmailThread records.

Architecture:
- No SQLAlchemy ORM events (they don't work with AsyncSession's session-per-request model).
- Instead: after a thread is upserted and committed, dispatch an asyncio.create_task()
  to run GPT-4o-mini classification in a fresh AsyncSession.
- This is a true fire-and-forget pattern — commit returns immediately,
  AI I/O happens out-of-band, existing threads never trigger re-classification.

Classification source priority:
  1. Gmail API messages (if credentials available)
  2. Stored emails from DB (always available if emails exist)
"""
import asyncio
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from app.models.thread import EmailThread, ThreadStatus
from app.models.email import Email
from app.services.thread_classifier import classify_thread_with_category
from app.services.gmail_service import parse_gmail_message


def _build_message_dict(email: Email) -> dict:
    """Convert a stored Email ORM object to a dict matching Gmail API format."""
    # Encode body_text so _decode_body can handle it (base64 urlsafe decode)
    import base64
    body_data = ""
    if email.body_text:
        try:
            body_data = base64.urlsafe_b64encode(email.body_text.encode("utf-8")).decode("ascii")
        except Exception:
            body_data = ""
    return {
        "id": email.gmail_message_id,
        "snippet": email.snippet or "",
        "payload": {
            "headers": [
                {"name": "From", "value": email.sender or ""},
                {"name": "Subject", "value": email.subject or ""},
            ],
            "body": {"data": body_data},
        },
    }


async def _classify_thread_async(
    user_id: int,
    gmail_thread_id: str,
    token: Optional[str],
    refresh_token: Optional[str],
) -> None:
    """
    Background task: run GPT-4o-mini classification using either Gmail API
    or stored DB emails, then update the EmailThread + Email records.
    """
    from app.core.database import AsyncSessionLocal
    from google.oauth2.credentials import Credentials

    async with AsyncSessionLocal() as db:
        try:
            # Re-fetch thread in this new session
            result = await db.execute(
                select(EmailThread).where(
                    EmailThread.user_id == user_id,
                    EmailThread.gmail_thread_id == gmail_thread_id,
                )
            )
            thread = result.scalar_one_or_none()
            if thread is None:
                return

            # Skip if already classified
            if thread.classification_confidence is not None:
                return

            messages: list[dict] = []

            # Source 1: Try Gmail API if credentials available
            if token:
                try:
                    from app.core.google import get_thread
                    credentials = Credentials(token=token, refresh_token=refresh_token)
                    gmail_thread = await get_thread(credentials, gmail_thread_id)
                    messages = gmail_thread.get("messages", [])
                except Exception as e:
                    print(f"[thread_events] Gmail API failed for {gmail_thread_id}: {e}")

            # Source 2: Fall back to stored emails from DB
            if not messages:
                emails_result = await db.execute(
                    select(Email).where(Email.email_thread_id == thread.id)
                )
                stored_emails = list(emails_result.scalars().all())
                if stored_emails:
                    messages = [_build_message_dict(e) for e in stored_emails]
                    # Update thread counters from stored emails
                    thread.message_count = len(stored_emails)
                    latest_ts: Optional[datetime] = None
                    for e in stored_emails:
                        if e.received_at and (latest_ts is None or e.received_at > latest_ts):
                            latest_ts = e.received_at
                    if latest_ts:
                        thread.last_message_at = latest_ts

            if not messages:
                # No data to classify — leave unclassified
                print(f"[thread_events] No messages for thread {gmail_thread_id}, skipping")
                return

            # Run AI classification
            classification_result, category_id = await classify_thread_with_category(
                thread_subject=thread.subject or "",
                thread_messages=messages,
                user_id=user_id,
                db=db,
            )

            # Map AI status to DB enum (lowercase values)
            try:
                db_status = ThreadStatus(classification_result.status.lower())
            except ValueError:
                db_status = ThreadStatus.INBOX

            thread.status = db_status
            thread.classification_confidence = classification_result.confidence
            thread.classification_reason = classification_result.reason
            thread.deadline = classification_result.deadline
            thread.category_id = category_id

            # Update all stored emails with classification results
            emails_result = await db.execute(
                select(Email).where(Email.email_thread_id == thread.id)
            )
            for email_record in emails_result.scalars().all():
                email_record.status = db_status
                email_record.classification_confidence = classification_result.confidence
                email_record.classification_reason = classification_result.reason
                email_record.category_id = category_id

            await db.commit()
            print(
                f"[thread_events] Classified thread {gmail_thread_id}: "
                f"{db_status.value} ({classification_result.confidence:.0%}) "
                f'"{classification_result.reason}"'
            )

        except Exception as e:
            print(f"[thread_events] Classification failed for thread {gmail_thread_id}: {e}")
            try:
                await db.rollback()
            except Exception:
                pass


def dispatch_classification(
    user_id: int,
    gmail_thread_id: str,
    token: Optional[str],
    refresh_token: Optional[str],
) -> None:
    """
    Fire-and-forget dispatcher — call this AFTER committing a new EmailThread.
    Creates an asyncio task that runs classification out-of-band.
    """
    asyncio.create_task(
        _classify_thread_async(user_id, gmail_thread_id, token, refresh_token)
    )


async def classify_existing_thread(
    user_id: int,
    gmail_thread_id: str,
    token: Optional[str],
    refresh_token: Optional[str],
) -> None:
    """
    Classify an existing thread that has no classification yet.
    Safe to call directly — used for retroactive classification.
    """
    await _classify_thread_async(user_id, gmail_thread_id, token, refresh_token)
