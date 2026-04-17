from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class EmailStatus(str, Enum):
    INBOX = "inbox"
    TODO = "todo"
    WAITING = "waiting"
    DONE = "done"


class EmailBase(BaseModel):
    subject: Optional[str] = None
    sender: Optional[str] = None
    sender_email: Optional[str] = None
    snippet: Optional[str] = None
    is_read: bool = False
    is_starred: bool = False
    category_id: Optional[int] = None
    status: EmailStatus = EmailStatus.INBOX


class EmailCreate(EmailBase):
    gmail_message_id: str
    history_id: Optional[str] = None
    thread_id: Optional[str] = None
    recipients: Optional[str] = None
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    label_ids: Optional[str] = None
    received_at: Optional[datetime] = None


class EmailUpdate(BaseModel):
    is_read: Optional[bool] = None
    is_starred: Optional[bool] = None
    category_id: Optional[int] = None
    status: Optional[EmailStatus] = None


class EmailResponse(EmailBase):
    id: int
    gmail_message_id: str
    history_id: Optional[str]
    thread_id: Optional[str]
    sender_email: Optional[str]
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    classification_confidence: Optional[float]
    classification_reason: Optional[str]
    received_at: Optional[datetime]
    synced_at: datetime

    class Config:
        from_attributes = True


class EmailListResponse(BaseModel):
    emails: List[EmailResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
