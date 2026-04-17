import base64
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Header, Depends, BackgroundTasks
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from google.oauth2.credentials import Credentials
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.database import get_db
from app.core.google import get_gmail_service
from app.models.user import User
from app.models.email import Email, EmailStatus
from app.models.thread import EmailThread
from app.models.category import Category
from app.schemas.email import EmailStatus as EmailStatusSchema
from app.services.gmail_watch import (
    parse_gmail_message,
    list_new_messages,
    fetch_message_by_id,
    watch_gmail_user,
    stop_gmail_watch,
)
from app.services.thread_events import dispatch_classification

router = APIRouter()
settings = get_settings()


class GmailWebhookPayload(BaseModel):
    email_address: str
    history_id: str


def _upsert_thread(
    user_id: int,
    gmail_thread_id: str,
    thread_subject: str,
    token: str,
    refresh_token: str | None,
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
        snippet="",
    )
    try:
        db.add(thread)
        db.flush()
        return thread, True
    except IntegrityError:
        db.rollback()
        result = db.execute(
            select(EmailThread).where(
                EmailThread.user_id == user_id,
                EmailThread.gmail_thread_id == gmail_thread_id,
            )
        )
        return result.scalar_one(), False


async def process_new_email(
    user_id: int,
    message_id: str,
    db: AsyncSession,
) -> Email | None:
    """
    Upsert a new email + thread.  For new threads, dispatches GPT-4o-mini
    classification as a fire-and-forget background task after commit.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.google_access_token:
        raise ValueError(f"No credentials for user {user_id}")

    credentials = Credentials(
        token=user.google_access_token,
        refresh_token=user.google_refresh_token,
    )

    gmail_message = await fetch_message_by_id(credentials, message_id)
    parsed = parse_gmail_message(gmail_message)

    # Skip already-synced email
    existing = await db.execute(
        select(Email).where(
            Email.user_id == user_id,
            Email.gmail_message_id == parsed["gmail_message_id"],
        )
    )
    if existing.scalar_one_or_none():
        return None

    gmail_thread_id = parsed.get("thread_id")
    thread_obj: EmailThread | None = None
    is_new_thread = False
    thread_token = credentials.token
    thread_refresh = credentials.refresh_token

    if gmail_thread_id:
        thread_obj, is_new_thread = _upsert_thread(
            user_id=user_id,
            gmail_thread_id=gmail_thread_id,
            thread_subject=parsed.get("subject") or "",
            token=thread_token,
            refresh_token=thread_refresh,
            db=db,
        )
        if not is_new_thread:
            thread_obj.message_count += 1
            if parsed.get("received_at"):
                ts = parsed["received_at"]
                received_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                if not thread_obj.last_message_at or received_dt > thread_obj.last_message_at:
                    thread_obj.last_message_at = received_dt

    received_at = None
    if parsed.get("received_at"):
        try:
            received_at = datetime.fromtimestamp(parsed["received_at"], tz=timezone.utc)
        except Exception:
            received_at = datetime.utcnow()

    email = Email(
        user_id=user_id,
        gmail_message_id=parsed["gmail_message_id"],
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
        status=thread_obj.status if thread_obj else EmailStatus.INBOX,
        classification_confidence=thread_obj.classification_confidence if thread_obj else None,
        classification_reason=thread_obj.classification_reason if thread_obj else None,
        category_id=thread_obj.category_id if thread_obj else None,
        is_read=parsed.get("is_read", False),
        is_starred=parsed.get("is_starred", False),
        received_at=received_at,
    )

    db.add(email)
    await db.commit()

    # Fire-and-forget: dispatch AI classification for new threads only
    if is_new_thread and gmail_thread_id:
        dispatch_classification(user_id, gmail_thread_id, thread_token, thread_refresh)

    await db.refresh(email)
    return email


async def handle_gmail_notification(
    email_address: str,
    history_id: str,
    db: AsyncSession,
) -> dict:
    result = await db.execute(select(User).where(User.email == email_address))
    user = result.scalar_one_or_none()

    if not user:
        return {"status": "ignored", "reason": "user_not_found"}
    if not user.google_access_token:
        return {"status": "ignored", "reason": "no_credentials"}

    credentials = Credentials(
        token=user.google_access_token,
        refresh_token=user.google_refresh_token,
    )

    # Get user's last known history_id
    recent_email = await db.execute(
        select(Email)
        .where(Email.user_id == user.id)
        .order_by(Email.created_at.desc())
        .limit(1)
    )
    recent = recent_email.scalar_one_or_none()
    last_history_id = recent.history_id if recent and recent.history_id else None

    if not last_history_id:
        service = get_gmail_service(credentials)
        profile = service.users().getProfile(userId="me").execute()
        last_history_id = history_id

    try:
        new_messages = await list_new_messages(credentials, last_history_id)
    except Exception as e:
        print(f"Error fetching new messages: {e}")
        new_messages = []

    processed_count = 0
    classification_results = []

    for msg in new_messages:
        try:
            email = await process_new_email(user.id, msg["id"], db)
            if email:
                processed_count += 1
                classification_results.append({
                    "message_id": msg["id"],
                    "status": email.status.value,
                    "category_id": email.category_id,
                })
        except Exception as e:
            print(f"Error processing message {msg['id']}: {e}")

    if history_id:
        await db.execute(
            update(User)
            .where(User.id == user.id)
            .values(google_token_expiry=datetime.utcnow())
        )
        await db.commit()

    return {
        "status": "processed",
        "user_id": user.id,
        "history_id": history_id,
        "new_messages": len(new_messages),
        "processed": processed_count,
        "classifications": classification_results,
    }


@router.post("/gmail")
async def gmail_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_goog_message_type: str = Header(None),
    x_goog_resource_id: str = Header(None),
    x_goog_resource_state: str = Header(None),
    x_goog_resource_checksum: str = Header(None),
    db: AsyncSession = Depends(get_db),
):
    if x_goog_message_type == "SYNC_MAIL_FOLDER":
        return {"message": "Mail sync notification received", "type": "sync"}

    if x_goog_message_type == "RECORD_PUBLISHED":
        body = await request.body()

        try:
            envelope = json.loads(body)
            email_message = envelope.get("message", {})
            data = base64.b64decode(email_message.get("data", ""))
            gmail_notification = json.loads(data)

            history_id = gmail_notification.get("historyId")
            email_address = gmail_notification.get("emailAddress")

            if not history_id or not email_address:
                raise HTTPException(status_code=400, detail="Invalid notification")

            background_tasks.add_task(
                handle_gmail_notification,
                email_address,
                history_id,
                db,
            )

            return {"status": "accepted", "history_id": history_id}

        except Exception as e:
            print(f"Error processing webhook: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    return {"message": "Notification type not recognized"}


@router.get("/gmail/verify")
async def verify_webhook(
    token: str = None,
    challenge: str = None,
):
    if not token or not challenge:
        raise HTTPException(status_code=400, detail="Missing parameters")

    if token != settings.gmail_webhook_verification_token:
        raise HTTPException(status_code=401, detail="Invalid token")

    return challenge


@router.post("/gmail/test")
async def test_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()
    email_address = body.get("email_address")
    history_id = body.get("history_id")

    if not email_address or not history_id:
        raise HTTPException(status_code=400, detail="Missing parameters")

    result = await handle_gmail_notification(email_address, history_id, db)
    return result
