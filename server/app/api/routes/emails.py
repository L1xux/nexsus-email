import asyncio
import json
from typing import Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from google.oauth2.credentials import Credentials

from app.core.database import get_db, AsyncSessionLocal
from app.core.config import get_settings
from app.models.user import User
from app.models.email import Email
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


@router.get("/sync-stream")
async def sync_stream(
    days: int = Query(7, ge=1, le=90),
    from_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    current_user: User = Depends(get_current_user_dep),
    credentials: Credentials = Depends(get_google_credentials),
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if from_date and to_date:
        try:
            start_dt = datetime.strptime(from_date, "%Y-%m-%d")
            end_dt = datetime.strptime(to_date, "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    else:
        end_dt = now
        start_dt = now - timedelta(days=days)

    chunks: list[tuple[datetime, datetime]] = []
    chunk_end = end_dt
    while chunk_end > start_dt:
        chunk_start = max(chunk_end - timedelta(days=2), start_dt)
        chunks.append((chunk_start, chunk_end))
        chunk_end = chunk_start

    user_id = current_user.id

    async def generate():
        import logging
        import traceback as tb
        logger = logging.getLogger(__name__)
        from app.services.email_sync import sync_gmail_emails
        for i, (cs, ce) in enumerate(chunks):
            try:
                async with AsyncSessionLocal() as db:
                    count = await sync_gmail_emails(
                        user_id, credentials, db,
                        max_results=200,
                        from_date=cs,
                        to_date=ce,
                    )
                event_data = json.dumps({
                    "chunk": i + 1,
                    "total": len(chunks),
                    "from_date": cs.strftime("%Y-%m-%d"),
                    "to_date": (ce - timedelta(days=1)).strftime("%Y-%m-%d"),
                    "new_count": count,
                })
            except Exception as e:
                logger.error(f"Sync chunk {i+1}/{len(chunks)} failed: {e}\n{tb.format_exc()}")
                event_data = json.dumps({
                    "chunk": i + 1,
                    "total": len(chunks),
                    "error": str(e),
                    "new_count": 0,
                })
            yield f"data: {event_data}\n\n"
            await asyncio.sleep(0)
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
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
    days: int = Query(7, ge=1, le=90, description="Sync emails from the last N days"),
    current_user: User = Depends(get_current_user_dep),
    credentials: Credentials = Depends(get_google_credentials),
    db: AsyncSession = Depends(get_db),
):
    try:
        from app.services.email_sync import sync_gmail_emails

        new_count = await sync_gmail_emails(current_user.id, credentials, db, max_results=200, days=days)

        return {"message": f"Synced {new_count} new emails"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync error: {str(e)}"
        )


