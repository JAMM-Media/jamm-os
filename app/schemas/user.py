from pydantic import BaseModel, EmailStr
from uuid import UUID
from typing import Optional

class UserBase(BaseModel):
    email: EmailStr
    is_active: bool = True

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserUpdate(BaseModel):
    password: Optional[str] = None
    is_active: Optional[bool] = None

class UserOut(UserBase):
    id: UUID

    class Config:
        from_attributes = True  # for Pydantic v2
