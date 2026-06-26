# app/schemas/user.py

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, ConfigDict

from app.core.enums import UserRole


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    is_active: bool = True
    role: UserRole = UserRole.staff


class UserCreate(UserBase):
    password: str
    # firm_id is injected from JWT in the endpoint — optional in the request body
    firm_id: Optional[UUID] = None


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    role: Optional[UserRole] = None
    cost_rate: Optional[float] = None


class UserOut(UserBase):
    id: UUID
    firm_id: UUID
    cost_rate: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)