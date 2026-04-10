from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.user import User
from app.models.email import Email, EmailStatus
from app.models.feedback import Feedback
from app.schemas.feedback import FeedbackResponse, FeedbackCreate
from app.schemas.email import EmailStatus as EmailStatusSchema
from app.api.dependencies import get_current_user_dep
from app.services.rag import save_feedback, initialize_rag
from app.services.classifier import get_email_status_enum

router = APIRouter()


@router.post("", response_model=FeedbackResponse)
async def create_feedback(
    feedback_data: FeedbackCreate,
    current_user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
):
    """
    Create feedback for an email classification.
    
    This endpoint:
    1. Updates the email's status in MariaDB if corrected
    2. Saves the feedback to Qdrant vector database for RAG
    """
    original_status = None
    original_category = None
    
    if feedback_data.email_id:
        result = await db.execute(
            select(Email).where(
                Email.id == feedback_data.email_id,
                Email.user_id == current_user.id
            )
        )
        email = result.scalar_one_or_none()
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")
        
        # Store original classification
        original_status = email.status.value if email.status else None
        
        # Get original category
        if email.category_id:
            from app.models.category import Category
            cat_result = await db.execute(
                select(Category).where(Category.id == email.category_id)
            )
            cat = cat_result.scalar_one_or_none()
            if cat:
                original_category = cat.name
        
        # Update email status if corrected_status provided
        if feedback_data.corrected_status:
            new_status = get_email_status_enum(feedback_data.corrected_status)
            email.status = new_status
    
    # Create feedback record
    feedback = Feedback(
        user_id=current_user.id,
        email_id=feedback_data.email_id,
        original_category=original_category,
        corrected_category=feedback_data.corrected_category or feedback_data.corrected_status,
        user_comment=feedback_data.user_comment,
        confidence_score=feedback_data.confidence_score,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    
    # Save to Qdrant for RAG
    if feedback_data.email_id and original_status:
        try:
            # Get email details for embedding
            email_result = await db.execute(
                select(Email).where(Email.id == feedback_data.email_id)
            )
            email = email_result.scalar_one_or_none()
            
            if email:
                vector_id = await save_feedback(
                    email_id=feedback_data.email_id,
                    sender=email.sender or "",
                    subject=email.subject or "",
                    body=email.body_text or "",
                    correct_status=feedback_data.corrected_status or feedback_data.corrected_category,
                    original_status=original_status,
                    user_comment=feedback_data.user_comment,
                )
                if vector_id:
                    feedback.vector_id = vector_id
                    await db.commit()
        except Exception as e:
            print(f"Failed to save feedback to Qdrant: {e}")
    
    return FeedbackResponse.model_validate(feedback)


@router.post("/correct-status")
async def correct_email_status(
    email_id: int,
    correct_status: str,
    comment: Optional[str] = None,
    current_user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
):
    """
    Quick endpoint to correct just the email status.
    
    Args:
        email_id: The email ID to correct
        correct_status: The correct status (ToDo/Waiting/Done)
        comment: Optional user comment
    """
    # Get email
    result = await db.execute(
        select(Email).where(
            Email.id == email_id,
            Email.user_id == current_user.id
        )
    )
    email = result.scalar_one_or_none()
    if not email:
        raise HTTPException(status_code=404, detail="Email not found")
    
    original_status = email.status.value if email.status else None
    
    # Update email status
    new_status = get_email_status_enum(correct_status)
    email.status = new_status
    
    # Create feedback record
    feedback = Feedback(
        user_id=current_user.id,
        email_id=email_id,
        corrected_category=correct_status,
        user_comment=comment,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    
    # Save to Qdrant
    try:
        vector_id = await save_feedback(
            email_id=email_id,
            sender=email.sender or "",
            subject=email.subject or "",
            body=email.body_text or "",
            correct_status=correct_status,
            original_status=original_status,
            user_comment=comment,
        )
        if vector_id:
            feedback.vector_id = vector_id
            await db.commit()
    except Exception as e:
        print(f"Failed to save to Qdrant: {e}")
    
    return {
        "message": "Status corrected",
        "email_id": email_id,
        "original_status": original_status,
        "new_status": correct_status,
        "feedback_id": feedback.id,
    }


@router.get("", response_model=list[FeedbackResponse])
async def list_feedback(
    current_user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
):
    """List all feedback for the current user."""
    result = await db.execute(
        select(Feedback)
        .where(Feedback.user_id == current_user.id)
        .order_by(Feedback.created_at.desc())
        .limit(100)
    )
    feedbacks = result.scalars().all()
    
    return [FeedbackResponse.model_validate(f) for f in feedbacks]


@router.post("/init-rag")
async def init_rag_system():
    """Initialize the RAG system - create Qdrant collection."""
    try:
        await initialize_rag()
        return {"status": "success", "message": "RAG system initialized"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize RAG: {str(e)}")
