from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(500), nullable=True)
    color = Column(String(7), default="#6366F1")
    is_system = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    user = relationship("User", back_populates="categories")
    emails = relationship("Email", back_populates="category")
    threads = relationship("EmailThread", back_populates="category")
