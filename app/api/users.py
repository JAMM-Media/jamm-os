# app/api/users.py

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from uuid import UUID

from app.db.session import get_db
from app.models.user import User
from app.models.firm import Firm
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.schemas.pagination import PaginatedResponse
from app.utils.pagination import paginate
from app.crud import user as crud_user
from app.dependencies.auth import get_current_user
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_firm_owner

router = APIRouter(prefix="/users", tags=["users"])


# -------------------------------------------------------------------
# POST /users/ — Create a new user
# Only firm_owner can add new staff to their firm.
# firm_id is injected from the JWT — not taken from the request body.
# -------------------------------------------------------------------
@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    existing = crud_user.get_user_by_email(db, email=user_in.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    # Override firm_id with the authenticated firm — never trust what's in the payload.
    user_in_with_firm = user_in.model_copy(update={"firm_id": current_firm.id})
    return crud_user.create_user(db, user_in_with_firm)


# -------------------------------------------------------------------
# GET /users/ — List all users in this firm
# -------------------------------------------------------------------
@router.get("/", response_model=PaginatedResponse[UserOut])
def list_users(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
    limit: int = Query(50, le=1000),
    offset: int = 0,
    desc: bool = False,
):
    query = db.query(User).filter(User.firm_id == current_firm.id)
    query = query.order_by(User.created_at.desc() if desc else User.created_at)
    return paginate(query, limit=limit, offset=offset)


# -------------------------------------------------------------------
# GET /users/me — Return the currently logged-in user
# MUST be defined before GET /users/{user_id}
# -------------------------------------------------------------------
@router.get("/me", response_model=UserOut)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user


# -------------------------------------------------------------------
# GET /users/{user_id} — Get a single user (must belong to same firm)
# -------------------------------------------------------------------
@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    user = db.query(User).filter(
        User.id == user_id,
        User.firm_id == current_firm.id,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# -------------------------------------------------------------------
# PATCH /users/{user_id} — Update a user
# -------------------------------------------------------------------
@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: UUID,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    user = db.query(User).filter(
        User.id == user_id,
        User.firm_id == current_firm.id,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return crud_user.update_user(db, user, user_in)


# -------------------------------------------------------------------
# DELETE /users/{user_id} — Delete a user
# -------------------------------------------------------------------
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    user = db.query(User).filter(
        User.id == user_id,
        User.firm_id == current_firm.id,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    crud_user.delete_user(db, user)