<<<<<<< HEAD
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

=======
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


class UserOut(UserBase):
    id: UUID
    firm_id: UUID
    firm_type: Optional[str] = None
    concierge_active: bool = False

>>>>>>> cb81db5 (fix: UserOut now includes firm_type and concierge_active sourced from the Firm row, not the User row, fixing the Concierge onboarding gate firing for every firm regardless of actual firm_type state)
    model_config = ConfigDict(from_attributes=True)