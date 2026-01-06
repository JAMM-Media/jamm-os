# app/api/users.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app.db.session import get_db
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.crud import user as crud_user
from app.core.security import oauth2_scheme
from jose import jwt, JWTError
from app.core.config import get_settings

router = APIRouter()
settings = get_settings()

# --- AUTH HELPER ---
def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(status_code=401, detail="Invalid token")
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return crud_user.get_user(db=next(get_db()), user_id=user_id)

# --- ROUTES ---
@router.post("/users/", response_model=UserOut)
def create_user(user_in: UserCreate, db: Session = Depends(get_db)):
    db_user = crud_user.get_user_by_email(db, email=user_in.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud_user.create_user(db, user_in)

@router.get("/users/", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db)):
    return crud_user.get_users(db)

@router.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: UUID, db: Session = Depends(get_db)):
    db_user = crud_user.get_user(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: UUID, user_in: UserUpdate, db: Session = Depends(get_db)):
    db_user = crud_user.get_user(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return crud_user.update_user(db, db_user, user_in)

@router.get("/users/me", response_model=UserOut)
def read_users_me(current_user=Depends(get_current_user)):
    return current_user

@router.delete("/users/{user_id}", status_code=204)
def delete_user(user_id: UUID, db: Session = Depends(get_db)):
    db_user = crud_user.get_user(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    crud_user.delete_user(db, db_user)

