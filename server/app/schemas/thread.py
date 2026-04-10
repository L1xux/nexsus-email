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
    is_read: bool = False
    is_starred: bool = False
    category_id: Optional[int] = None
    status: ThreadStatus = ThreadStatus.INBOX


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
    is_read: bool
    is_starred: bool
    received_at: Optional[datetime]

    class Config:
        from_attributes = True


class ThreadResponse(ThreadBase):
    id: int
    gmail_thread_id: str
    participant_count: int
    message_count: int
    classification_confidence: Optional[float]
    classification_reason: Optional[str]
    last_message_at: Optional[datetime]
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
