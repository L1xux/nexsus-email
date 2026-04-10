import base64
import json
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Header, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from google.oauth2.credentials import Credentials
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.models.email import Email, EmailStatus
from app.models.category import Category
from app.schemas.email import EmailStatus as EmailStatusSchema
from app.services.gmail_watch import (
    parse_gmail_message,
    list_new_messages,
    fetch_message_by_id,
    watch_gmail_user,
    stop_gmail_watch,
)
from app.services.classifier import (
    classify_email,
    classify_category,
    get_email_status_enum,
    ClassificationResult,
)

router = APIRouter()
settings = get_settings()


class GmailWebhookPayload(BaseModel):
    email_address: str
    history_id: str


async def process_new_email(
    user_id: int,
    message_id: str,
    db: AsyncSession,
) -> Email:
    """
    Process a single new email: fetch, classify (status + category), and save to database.
    """
    from app.models.user import User
    
    # Get user's Google credentials
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    
    if not user or not user.google_access_token:
        raise ValueError(f"No credentials for user {user_id}")
    
    credentials = Credentials(
        token=user.google_access_token,
        refresh_token=user.google_refresh_token,
    )
    
    # Fetch the full message
    gmail_message = await fetch_message_by_id(credentials, message_id)
    parsed = parse_gmail_message(gmail_message)
    
    # Check if email already exists
    existing = await db.execute(
        select(Email).where(
            Email.user_id == user_id,
            Email.gmail_message_id == parsed["gmail_message_id"],
        )
    )
    if existing.scalar_one_or_none():
        return None
    
    # Classify email status (ToDo/Waiting/Done)
    status_classification: ClassificationResult = await classify_email(
        subject=parsed.get("subject", ""),
        sender=parsed.get("sender", ""),
        body=parsed.get("body_text", ""),
        user_id=user_id,
        db=db,
    )
    
    # Convert status string to enum
    email_status = get_email_status_enum(status_classification.status)
    
    # Classify email category
    category_name, category_confidence = await classify_category(
        subject=parsed.get("subject", ""),
        sender=parsed.get("sender", ""),
        body=parsed.get("body_text", ""),
        user_id=user_id,
        db=db,
    )
    
    # Find category
    cat_result = await db.execute(
        select(Category).where(
            Category.user_id == user_id,
            Category.name == category_name,
        )
    )
    category = cat_result.scalar_one_or_none()
    category_id = category.id if category else None
    
    # Parse received_at
    received_at = None
    if parsed.get("received_at"):
        try:
            received_at = datetime.fromisoformat(parsed["received_at"])
        except:
            received_at = datetime.utcnow()
    
    # Create email record with classification results
    email = Email(
        user_id=user_id,
        gmail_message_id=parsed["gmail_message_id"],
        history_id=parsed.get("history_id"),
        thread_id=parsed.get("thread_id"),
        subject=parsed.get("subject"),
        sender=parsed.get("sender"),
        sender_email=parsed.get("sender_email"),
        recipients=parsed.get("recipients"),
        snippet=parsed.get("snippet"),
        body_text=parsed.get("body_text"),
        body_html=parsed.get("body_html"),
        label_ids=parsed.get("label_ids"),
        category_id=category_id,
        status=email_status,
        classification_confidence=status_classification.confidence,
        classification_reason=status_classification.reason,
        is_read=parsed.get("is_read", False),
        is_starred=parsed.get("is_starred", False),
        received_at=received_at,
    )
    
    db.add(email)
    await db.commit()
    await db.refresh(email)
    
    return email


async def handle_gmail_notification(
    email_address: str,
    history_id: str,
    db: AsyncSession,
) -> dict:
    """
    Handle incoming Gmail webhook notification.
    Fetches new messages and processes each through the classification pipeline.
    """
    # Find user by email
    result = await db.execute(select(User).where(User.email == email_address))
    user = result.scalar_one_or_none()
    
    if not user:
        return {"status": "ignored", "reason": "user_not_found"}
    
    if not user.google_access_token:
        return {"status": "ignored", "reason": "no_credentials"}
    
    # Get credentials
    credentials = Credentials(
        token=user.google_access_token,
        refresh_token=user.google_refresh_token,
    )
    
    # Get user's last known history_id from database
    last_history_id = None
    
    # Fetch the most recent email to get the latest history_id
    recent_email = await db.execute(
        select(Email)
        .where(Email.user_id == user.id)
        .order_by(Email.created_at.desc())
        .limit(1)
    )
    recent = recent_email.scalar_one_or_none()
    if recent and recent.history_id:
        last_history_id = recent.history_id
    
    # If no last_history_id, use current historyId as starting point
    if not last_history_id:
        from app.services.gmail_watch import get_gmail_service
        service = get_gmail_service(credentials)
        profile = service.users().getProfile(userId="me").execute()
        last_history_id = history_id
    
    # Get new messages since last sync
    try:
        new_messages = await list_new_messages(credentials, last_history_id)
    except Exception as e:
        print(f"Error fetching new messages: {e}")
        new_messages = []
    
    # Process each new message through classification pipeline
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
    
    # Update user's last sync timestamp
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
    """
    Gmail Pub/Sub webhook endpoint.
    Receives POST requests from Google Cloud Pub/Sub when new emails arrive.
    Triggers AI classification pipeline for each new email.
    """
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
            
            # Process in background to respond quickly to Pub/Sub
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
    """
    Google Pub/Sub verification endpoint.
    Used to verify ownership of the webhook URL.
    """
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
    """
    Test webhook endpoint for development.
    Simulates receiving a webhook notification and triggers classification.
    """
    body = await request.json()
    email_address = body.get("email_address")
    history_id = body.get("history_id")
    
    if not email_address or not history_id:
        raise HTTPException(status_code=400, detail="Missing parameters")
    
    result = await handle_gmail_notification(email_address, history_id, db)
    
    return result


@router.post("/classify")
async def test_classification(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Test endpoint to classify a single email without webhook.
    Useful for testing the classification pipeline.
    """
    body = await request.json()
    subject = body.get("subject", "")
    sender = body.get("sender", "")
    body_text = body.get("body", "")
    
    # Classify status
    status_result = await classify_email(subject, sender, body_text, 0, db)
    
    # Classify category
    category_name, category_confidence = await classify_category(subject, sender, body_text, 0, db)
    
    return {
        "status_classification": {
            "status": status_result.status,
            "confidence": status_result.confidence,
            "reason": status_result.reason,
        },
        "category_classification": {
            "category": category_name,
            "confidence": category_confidence,
        }
    }
