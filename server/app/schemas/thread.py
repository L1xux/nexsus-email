from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ThreadStatus(str, Enum):
    INBOX = "inbox"
    TODO = "todo"
    WAITING = "waiting"
    DONE = "done"


class ThreadBase(BaseModel):
    subject: Optional[str] = None
    snippet: Optional[str] = None
    is_read: Optional[bool] = False
    is_starred: Optional[bool] = False
    category_id: Optional[int] = None
    status: ThreadStatus = ThreadStatus.INBOX
    deadline: Optional[datetime] = None


class ThreadUpdate(BaseModel):
    is_read: Optional[bool] = None
    is_starred: Optional[bool] = None
    category_id: Optional[int] = None
    status: Optional[ThreadStatus] = None


class EmailInThread(BaseModel):
    id: int
    gmail_message_id: str
    sender: Optional[str]
    sender_email: Optional[str]
    snippet: Optional[str]
    body_text: Optional[str] = None
    body_html: Optional[str] = None
    is_read: Optional[bool] = False
    is_starred: Optional[bool] = False
    received_at: Optional[datetime]

    class Config:
        from_attributes = True


class ThreadResponse(ThreadBase):
    id: int
    gmail_thread_id: str
    participant_count: Optional[int] = 1
    message_count: Optional[int] = 1
    classification_confidence: Optional[float] = None
    classification_reason: Optional[str] = None
    last_message_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ThreadWithEmails(ThreadResponse):
    emails: List[EmailInThread] = []

    class Config:
        from_attributes = True


class ThreadListResponse(BaseModel):
    threads: List[ThreadResponse]
    total: int
    page: int
    page_size: int
    has_next: bool
