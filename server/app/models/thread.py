import enum
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class ThreadStatus(str, enum.Enum):
    INBOX = "inbox"
    TODO = "todo"
    WAITING = "waiting"
    DONE = "done"


class EmailThread(Base):
    __tablename__ = "threads"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    gmail_thread_id = Column(String(255), unique=True, index=True, nullable=False)
    subject = Column(String(500), nullable=True)
    participant_count = Column(Integer, default=1)
    message_count = Column(Integer, default=1)
    snippet = Column(Text, nullable=True)
    status = Column(String(20), default="inbox", index=True)
    classification_confidence = Column(Float, nullable=True)
    classification_reason = Column(String(500), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    is_read = Column(Boolean, default=False, index=True)
    is_starred = Column(Boolean, default=False, index=True)
    last_message_at = Column(DateTime, nullable=True, index=True)
    deadline = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="threads")
    category = relationship("Category", back_populates="threads")
    emails = relationship("Email", back_populates="thread", cascade="all, delete-orphan")
