from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from google.oauth2.credentials import Credentials

from app.core.database import get_db
from app.core.google import get_gmail_service, get_email as gmail_get_email
from app.core.config import get_settings
from app.models.user import User
from app.models.email import Email, EmailStatus
from app.models.category import Category
from app.schemas.email import EmailResponse, EmailListResponse, EmailUpdate, EmailStatus as EmailStatusSchema
from app.api.dependencies import get_current_user_dep, get_google_credentials

router = APIRouter()
settings = get_settings()


@router.get("", response_model=EmailListResponse)
async def list_emails(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: Optional[int] = None,
    is_read: Optional[bool] = None,
    status: Optional[EmailStatusSchema] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(Email).where(Email.user_id == current_user.id)
    
    if category_id:
        query = query.where(Email.category_id == category_id)
    if is_read is not None:
        query = query.where(Email.is_read == is_read)
    if status is not None:
        query = query.where(Email.status == status)
    if search:
        query = query.where(Email.subject.ilike(f"%{search}%"))
    
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    query = query.order_by(desc(Email.received_at)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    emails = result.scalars().all()
    
    return EmailListResponse(
        emails=[EmailResponse.model_validate(e) for e in emails],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


@router.get("/{email_id}", response_model=EmailResponse)
async def get_email(
    email_id: int,
    current_user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Email).where(Email.id == email_id, Email.user_id == current_user.id)
    )
    email = result.scalar_one_or_none()
    
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    
    return EmailResponse.model_validate(email)


@router.patch("/{email_id}", response_model=EmailResponse)
async def update_email(
    email_id: int,
    email_update: EmailUpdate,
    current_user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Email).where(Email.id == email_id, Email.user_id == current_user.id)
    )
    email = result.scalar_one_or_none()
    
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    
    if email_update.is_read is not None:
        email.is_read = email_update.is_read
    if email_update.is_starred is not None:
        email.is_starred = email_update.is_starred
    if email_update.status is not None:
        email.status = email_update.status
    if email_update.category_id is not None:
        result = await db.execute(
            select(Category).where(
                Category.id == email_update.category_id,
                Category.user_id == current_user.id
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Category not found")
        email.category_id = email_update.category_id
    
    await db.commit()
    await db.refresh(email)
    
    return EmailResponse.model_validate(email)


@router.post("/sync")
async def sync_emails(
    current_user: User = Depends(get_current_user_dep),
    credentials: Credentials = Depends(get_google_credentials),
    db: AsyncSession = Depends(get_db),
):
    from app.services.email_sync import sync_gmail_emails
    
    new_count = await sync_gmail_emails(current_user.id, credentials, db)
    
    return {"message": f"Synced {new_count} new emails"}


@router.post("/seed")
async def seed_test_emails(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).limit(1))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=401, detail="No user found")
    
    test_emails = [
        Email(
            user_id=user.id,
            gmail_message_id=f"test-{i}",
            subject=f"Test Email {i}",
            sender=f"Sender {i}",
            sender_email=f"sender{i}@example.com",
            snippet=f"This is test email number {i}",
            body_text=f"Body of test email {i}",
            status=EmailStatus.INBOX,
            is_read=False,
            received_at=datetime.utcnow(),
        )
        for i in range(1, 11)
    ]
    
    db.add_all(test_emails)
    await db.commit()
    
    return {"message": f"Created {len(test_emails)} test emails"}
