from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class FeedbackBase(BaseModel):
    corrected_category: Optional[str] = None
    corrected_status: Optional[str] = None
    user_comment: Optional[str] = None


class FeedbackCreate(FeedbackBase):
    email_id: Optional[int] = None
    original_category: Optional[str] = None
    confidence_score: Optional[float] = None


class FeedbackResponse(FeedbackBase):
    id: int
    user_id: int
    email_id: Optional[int]
    original_category: Optional[str]
    confidence_score: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True
