from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from sqlalchemy.orm import selectinload
from google.oauth2.credentials import Credentials

from app.core.database import get_db
from app.core.config import get_settings
from app.models.user import User
from app.models.thread import EmailThread, ThreadStatus
from app.models.category import Category
from app.schemas.thread import (
    ThreadResponse,
    ThreadWithEmails,
    ThreadUpdate,
    ThreadListResponse,
    ThreadStatus as ThreadStatusSchema,
)
from app.api.dependencies import get_current_user_dep, get_google_credentials
from app.services.thread_events import dispatch_classification

settings = get_settings()

router = APIRouter()


@router.get("", response_model=ThreadListResponse)
async def list_threads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=500),
    category_id: Optional[int] = None,
    is_read: Optional[bool] = None,
    status: Optional[ThreadStatusSchema] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
):
    query = select(EmailThread).where(EmailThread.user_id == current_user.id)
    
    if category_id:
        query = query.where(EmailThread.category_id == category_id)
    if is_read is not None:
        query = query.where(EmailThread.is_read == is_read)
    if status is not None:
        query = query.where(EmailThread.status == ThreadStatus(status.value))
    if search:
        query = query.where(EmailThread.subject.ilike(f"%{search}%"))
    
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)
    
    query = query.order_by(desc(EmailThread.last_message_at)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    threads = result.scalars().all()
    
    return ThreadListResponse(
        threads=[ThreadResponse.model_validate(t) for t in threads],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


@router.get("/{thread_id}", response_model=ThreadWithEmails)
async def get_thread(
    thread_id: int,
    current_user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EmailThread)
        .where(
            EmailThread.id == thread_id,
            EmailThread.user_id == current_user.id
        )
        .options(selectinload(EmailThread.emails))
    )
    thread = result.scalar_one_or_none()
    
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    return ThreadWithEmails.model_validate(thread)


@router.patch("/{thread_id}", response_model=ThreadResponse)
async def update_thread(
    thread_id: int,
    thread_update: ThreadUpdate,
    current_user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(EmailThread).where(
            EmailThread.id == thread_id,
            EmailThread.user_id == current_user.id
        )
    )
    thread = result.scalar_one_or_none()
    
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    
    if thread_update.is_read is not None:
        thread.is_read = thread_update.is_read
    if thread_update.is_starred is not None:
        thread.is_starred = thread_update.is_starred
    if thread_update.status is not None:
        thread.status = ThreadStatus(thread_update.status.value.lower())
    if thread_update.category_id is not None:
        cat_result = await db.execute(
            select(Category).where(
                Category.id == thread_update.category_id,
                Category.user_id == current_user.id
            )
        )
        if not cat_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Category not found")
        thread.category_id = thread_update.category_id
    
    await db.commit()
    await db.refresh(thread)
    
    return ThreadResponse.model_validate(thread)


@router.post("/{thread_id}/refresh")
async def refresh_thread(
    thread_id: int,
    current_user: User = Depends(get_current_user_dep),
    credentials: Credentials = Depends(get_google_credentials),
    db: AsyncSession = Depends(get_db),
):
    from app.services.email_sync import sync_and_classify_thread

    result = await db.execute(
        select(EmailThread).where(
            EmailThread.id == thread_id,
            EmailThread.user_id == current_user.id
        )
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")

    await sync_and_classify_thread(
        user_id=current_user.id,
        gmail_thread_id=thread.gmail_thread_id,
        credentials=credentials,
        db=db,
    )

    await db.refresh(thread)

    return {"message": "Thread refreshed", "status": thread.status.value}


@router.post("/classify-all")
async def classify_all_threads(
    current_user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
):
    """
    Dispatch AI classification for all unclassified threads.
    Uses Gmail API if credentials available; falls back to stored emails otherwise.
    """
    # Optional credentials — not required since we can classify from stored emails
    token: Optional[str] = None
    refresh_token: Optional[str] = None
    if current_user.google_access_token:
        token = current_user.google_access_token
        refresh_token = current_user.google_refresh_token

    result = await db.execute(
        select(EmailThread).where(
            EmailThread.user_id == current_user.id,
            EmailThread.classification_confidence.is_(None),
        )
    )
    threads = result.scalars().all()

    dispatched = 0
    for thread in threads:
        dispatch_classification(
            user_id=current_user.id,
            gmail_thread_id=thread.gmail_thread_id,
            token=token,
            refresh_token=refresh_token,
        )
        dispatched += 1

    return {
        "message": f"Dispatched classification for {dispatched} threads",
        "dispatched": dispatched,
        "total": len(threads),
        "source": "gmail_api" if token else "stored_emails",
    }
