from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


# ──── User Schemas ────

class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    mobile_number: Optional[str] = None
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    full_name: str
    email: str
    mobile_number: Optional[str] = None
    role: str = "user"
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


# ──── Item Schemas ────

class ItemCreate(BaseModel):
    title: str
    description: Optional[str] = None
    category: str  # "LOST" or "FOUND"
    location: Optional[str] = None
    date_reported: Optional[str] = None
    image_url: Optional[str] = None  # Base64 image data


class ItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None
    image_url: Optional[str] = None


class ItemOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    category: str
    location: Optional[str] = None
    date_reported: Optional[str] = None
    status: str
    image_url: Optional[str] = None
    contact_email: Optional[str] = None
    user_id: int
    created_at: datetime
    owner_name: Optional[str] = None
    owner_email: Optional[str] = None
    owner_mobile: Optional[str] = None

    class Config:
        from_attributes = True


class ClaimRequest(BaseModel):
    finder_name: str
    finder_email: str
    message: Optional[str] = None


# ──── Admin Schemas ────

class AdminUserUpdate(BaseModel):
    role: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None


class StatsOut(BaseModel):
    total_users: int
    total_items: int
    lost_items: int
    found_items: int
    open_items: int
    claimed_items: int
    closed_items: int
