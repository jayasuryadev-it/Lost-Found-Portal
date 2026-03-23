import os
from typing import Optional, List

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database import engine, get_db, Base, SessionLocal
from models import User, Item, ItemCategory, ItemStatus
from sqlalchemy import func as sa_func
from schemas import (
    UserCreate, UserLogin, UserOut, Token,
    ItemCreate, ItemOut, ItemUpdate, ClaimRequest,
    AdminUserUpdate, StatsOut
)
from auth import get_password_hash, verify_password, create_access_token, get_current_user, get_current_admin
from matcher import process_found_item_matches

load_dotenv()

# ──── Create tables ────
Base.metadata.create_all(bind=engine)

# ──── App ────
app = FastAPI(title="Lost & Found Portal", version="1.0.0")

# ──── CORS ────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════
# AUTH ROUTES
# ═══════════════════════════════════════════════════════════

@app.post("/api/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user."""
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    db_user = User(
        full_name=user.full_name,
        email=user.email,
        mobile_number=user.mobile_number,
        hashed_password=get_password_hash(user.password),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.post("/api/login", response_model=Token)
def login(user: UserLogin, db: Session = Depends(get_db)):
    """Login and receive JWT token."""
    db_user = db.query(User).filter(User.email == user.email).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": db_user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    """Get the currently logged-in user's profile."""
    return current_user


# ═══════════════════════════════════════════════════════════
# ITEM ROUTES
# ═══════════════════════════════════════════════════════════

def item_to_response(item: Item) -> dict:
    """Convert an Item model to response dict with owner info."""
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "category": item.category.value if isinstance(item.category, ItemCategory) else item.category,
        "location": item.location,
        "date_reported": item.date_reported,
        "status": item.status.value if isinstance(item.status, ItemStatus) else item.status,
        "image_url": item.image_url,
        "contact_email": item.contact_email,
        "user_id": item.user_id,
        "created_at": item.created_at,
        "owner_name": item.owner.full_name if item.owner else None,
        "owner_email": item.owner.email if item.owner else None,
        "owner_mobile": item.owner.mobile_number if item.owner else None,
    }


@app.post("/api/items", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(
    item: ItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new lost or found item listing."""
    try:
        category = ItemCategory(item.category.upper())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid category '{item.category}'. Must be LOST or FOUND.",
        )
    
    db_item = Item(
        title=item.title,
        description=item.description,
        category=category,
        location=item.location,
        date_reported=item.date_reported,
        status=ItemStatus.OPEN,
        image_url=item.image_url,
        contact_email=current_user.email,
        user_id=current_user.id,
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)

    # Auto-match: when a FOUND item is posted, find matching LOST items and notify
    if category == ItemCategory.FOUND:
        match_count = process_found_item_matches(db_item, current_user, db)
        if match_count > 0:
            print(f"Auto-matched: notified {match_count} lost item owner(s)")

    return item_to_response(db_item)


@app.get("/api/items", response_model=List[ItemOut])
def list_items(
    category: Optional[str] = None,
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List all items with optional filters."""
    query = db.query(Item)

    if category:
        try:
            query = query.filter(Item.category == ItemCategory(category.upper()))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid category '{category}'. Must be LOST or FOUND.",
            )

    if status_filter:
        try:
            query = query.filter(Item.status == ItemStatus(status_filter.upper()))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid status '{status_filter}'. Must be OPEN, CLAIMED, or CLOSED.",
            )
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                Item.title.ilike(search_term),
                Item.description.ilike(search_term),
                Item.location.ilike(search_term),
            )
        )
    
    items = query.order_by(Item.created_at.desc()).all()
    return [item_to_response(item) for item in items]


@app.get("/api/items/{item_id}", response_model=ItemOut)
def get_item(item_id: int, db: Session = Depends(get_db)):
    """Get a single item by ID."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item_to_response(item)


@app.put("/api/items/{item_id}", response_model=ItemOut)
def update_item(
    item_id: int,
    item_update: ItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an item (owner only)."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this item")
    
    update_data = item_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "status" and value:
            setattr(item, key, ItemStatus(value.upper()))
        else:
            setattr(item, key, value)
    
    db.commit()
    db.refresh(item)
    return item_to_response(item)


@app.delete("/api/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an item (owner only)."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this item")
    
    db.delete(item)
    db.commit()
    return None


@app.post("/api/items/{item_id}/claim", response_model=ItemOut)
def claim_item(
    item_id: int,
    claim: ClaimRequest,
    db: Session = Depends(get_db),
):
    """Mark an item as claimed (someone found it). Frontend handles email via EmailJS."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.status != ItemStatus.OPEN:
        raise HTTPException(status_code=400, detail="Item is already claimed or closed")
    
    item.status = ItemStatus.CLAIMED
    db.commit()
    db.refresh(item)
    
    return item_to_response(item)


@app.get("/api/my-items", response_model=List[ItemOut])
def my_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all items posted by the current user."""
    items = db.query(Item).filter(Item.user_id == current_user.id).order_by(Item.created_at.desc()).all()
    return [item_to_response(item) for item in items]


# ═══════════════════════════════════════════════════════════
# ADMIN ROUTES
# ═══════════════════════════════════════════════════════════

@app.get("/api/admin/stats", response_model=StatsOut)
def admin_stats(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Get dashboard statistics."""
    total_users = db.query(sa_func.count(User.id)).scalar()
    total_items = db.query(sa_func.count(Item.id)).scalar()
    lost_items = db.query(sa_func.count(Item.id)).filter(Item.category == ItemCategory.LOST).scalar()
    found_items = db.query(sa_func.count(Item.id)).filter(Item.category == ItemCategory.FOUND).scalar()
    open_items = db.query(sa_func.count(Item.id)).filter(Item.status == ItemStatus.OPEN).scalar()
    claimed_items = db.query(sa_func.count(Item.id)).filter(Item.status == ItemStatus.CLAIMED).scalar()
    closed_items = db.query(sa_func.count(Item.id)).filter(Item.status == ItemStatus.CLOSED).scalar()
    return StatsOut(
        total_users=total_users, total_items=total_items,
        lost_items=lost_items, found_items=found_items,
        open_items=open_items, claimed_items=claimed_items, closed_items=closed_items,
    )


@app.get("/api/admin/users", response_model=List[UserOut])
def admin_list_users(
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """List all users (admin only)."""
    query = db.query(User)
    if search:
        term = f"%{search}%"
        query = query.filter(or_(User.full_name.ilike(term), User.email.ilike(term)))
    return query.order_by(User.created_at.desc()).all()


@app.put("/api/admin/users/{user_id}", response_model=UserOut)
def admin_update_user(
    user_id: int,
    update: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Update a user's role or info (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id and update.role and update.role != "admin":
        raise HTTPException(status_code=400, detail="Cannot remove your own admin role")
    update_data = update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user


@app.delete("/api/admin/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Delete a user and all their items (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    db.query(Item).filter(Item.user_id == user.id).delete()
    db.delete(user)
    db.commit()
    return None


@app.get("/api/admin/items", response_model=List[ItemOut])
def admin_list_items(
    category: Optional[str] = None,
    status_filter: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """List all items (admin view)."""
    query = db.query(Item)
    if category:
        try:
            query = query.filter(Item.category == ItemCategory(category.upper()))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid category '{category}'")
    if status_filter:
        try:
            query = query.filter(Item.status == ItemStatus(status_filter.upper()))
        except ValueError:
            raise HTTPException(status_code=422, detail=f"Invalid status '{status_filter}'")
    if search:
        term = f"%{search}%"
        query = query.filter(or_(Item.title.ilike(term), Item.description.ilike(term), Item.location.ilike(term)))
    items = query.order_by(Item.created_at.desc()).all()
    return [item_to_response(item) for item in items]


@app.put("/api/admin/items/{item_id}", response_model=ItemOut)
def admin_update_item(
    item_id: int,
    item_update: ItemUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Update any item (admin only, no ownership check)."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    update_data = item_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "status" and value:
            setattr(item, key, ItemStatus(value.upper()))
        else:
            setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item_to_response(item)


@app.delete("/api/admin/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Delete any item (admin only)."""
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return None


# ═══════════════════════════════════════════════════════════
# STARTUP: Seed admin user from env
# ═══════════════════════════════════════════════════════════

@app.on_event("startup")
def seed_admin():
    """Promote a user to admin based on ADMIN_EMAIL env var."""
    admin_email = os.getenv("ADMIN_EMAIL")
    if not admin_email:
        return
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == admin_email).first()
        if user and user.role != "admin":
            user.role = "admin"
            db.commit()
            print(f"Promoted {admin_email} to admin")
    finally:
        db.close()


# ──── Health Check ────
@app.get("/api/health")
def health():
    return {"status": "ok", "message": "Lost & Found Portal API is running"}
