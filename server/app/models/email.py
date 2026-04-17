import enum
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class EmailStatus(str, enum.Enum):
    INBOX = "inbox"
    TODO = "todo"
    WAITING = "waiting"
    DONE = "done"


class Email(Base):
    __tablename__ = "emails"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    gmail_message_id = Column(String(255), unique=True, index=True, nullable=False)
    history_id = Column(String(255), nullable=True, index=True)
    thread_id = Column(String(255), nullable=True, index=True)
    email_thread_id = Column(Integer, ForeignKey("threads.id", ondelete="CASCADE"), nullable=True, index=True)
    subject = Column(String(500), nullable=True)
    sender = Column(String(255), nullable=True)
    sender_email = Column(String(255), nullable=True, index=True)
    recipients = Column(Text, nullable=True)
    snippet = Column(Text, nullable=True)
    body_text = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    label_ids = Column(Text, nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(20), default="inbox", index=True)
    classification_confidence = Column(Float, nullable=True)
    classification_reason = Column(String(500), nullable=True)
    is_read = Column(Boolean, default=False, index=True)
    is_starred = Column(Boolean, default=False, index=True)
    received_at = Column(DateTime, nullable=True, index=True)
    synced_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="emails")
    thread = relationship("EmailThread", back_populates="emails")
    category = relationship("Category", back_populates="emails")
