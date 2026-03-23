from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from database import Base


class ItemCategory(str, enum.Enum):
    LOST = "LOST"
    FOUND = "FOUND"


class ItemStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLAIMED = "CLAIMED"
    CLOSED = "CLOSED"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    mobile_number = Column(String(20), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, server_default="user")  # "user" or "admin"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    items = relationship("Item", back_populates="owner")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(SAEnum(ItemCategory), nullable=False)
    location = Column(String(255), nullable=True)
    date_reported = Column(String(50), nullable=True)
    status = Column(SAEnum(ItemStatus), default=ItemStatus.OPEN)
    image_url = Column(Text, nullable=True)  # Base64 encoded image or URL
    contact_email = Column(String(255), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    owner = relationship("User", back_populates="items")
