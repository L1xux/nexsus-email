from datetime import datetime, timedelta, timezone
from typing import Optional

from google.oauth2.credentials import Credentials
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email import Email
from app.models.thread import EmailThread
from app.models.user import User
from app.services.gmail_service import fetch_recent_emails, parse_gmail_message
from app.services.thread_events import dispatch_classification


async def _upsert_thread(
    user_id: int,
    gmail_thread_id: str,
    thread_subject: Optional[str],
    thread_snippet: Optional[str],
    token: str,
    refresh_token: Optional[str],
    db: AsyncSession,
) -> tuple[EmailThread, bool]:
    """
    Clean INSERT-or-skip using unique-constraint violation.
    Returns (thread, is_new).  Call dispatch_classification() for new threads
    AFTER the session commits.
    """
    thread = EmailThread(
        user_id=user_id,
        gmail_thread_id=gmail_thread_id,
        subject=thread_subject,
        snippet=thread_snippet,
    )
    try:
        db.add(thread)
        await db.flush()
        return thread, True  # new thread
    except IntegrityError:
        await db.rollback()
        result = await db.execute(
            select(EmailThread).where(
                EmailThread.user_id == user_id,
                EmailThread.gmail_thread_id == gmail_thread_id,
            )
        )
        return result.scalar_one(), False  # existing thread


def _parse_received_at(date_value) -> Optional[datetime]:
    if not date_value:
        return None
    try:
        if isinstance(date_value, (int, float)):
            return datetime.fromtimestamp(date_value, tz=timezone.utc)
        if isinstance(date_value, str):
            return datetime.strptime(date_value, "%a %b %d %H:%M:%S %Y")
    except (ValueError, TypeError, OSError):
        pass
    return None


async def sync_gmail_emails(
    user_id: int,
    credentials: Credentials,
    db: AsyncSession,
    max_results: int = 50,
    days: int = 3,
) -> int:
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        return 0

    after_date = datetime.now(timezone.utc) - timedelta(days=days)
    query = f"after:{after_date.strftime('%Y/%m/%d')}"
    emails_data = await fetch_recent_emails(credentials, max_results, query=query)

    new_count = 0
    thread_cache: dict[str, EmailThread] = {}
    new_threads: list[tuple[str, str, Optional[str]]] = []  # (gmail_tid, token, refresh)
    token = credentials.token
    refresh_t = credentials.refresh_token

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

        thread_obj: Optional[EmailThread] = None
        is_new = False
        if gmail_thread_id:
            if gmail_thread_id in thread_cache:
                thread_obj = thread_cache[gmail_thread_id]
            else:
                thread_obj, is_new = await _upsert_thread(
                    user_id=user_id,
                    gmail_thread_id=gmail_thread_id,
                    thread_subject=parsed.get("subject"),
                    thread_snippet=parsed.get("snippet"),
                    token=token,
                    refresh_token=refresh_t,
                    db=db,
                )
                thread_cache[gmail_thread_id] = thread_obj
                if is_new:
                    new_threads.append((gmail_thread_id, token, refresh_t))

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

    # Dispatch AI classification for every newly-created thread (fire-and-forget)
    for gmail_tid, t, rt in new_threads:
        dispatch_classification(user_id, gmail_tid, t, rt)

    return new_count


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
