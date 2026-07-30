# app/crud/user.py

from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.enums import UserRole
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email).first()


def get_firm_owners_and_managers(db: Session, firm_id: UUID) -> list[User]:
    """
    Active firm_owner and manager users for one firm.

    This is the recipient set for firm-level operational and compliance
    notices. Staff are excluded deliberately rather than incidentally: the
    IrsAuthorization model's RBAC is firm_owner and manager only, so a staff
    user cannot open the record a warning points at.
    """
    return list(db.execute(
        select(User).where(
            User.firm_id == firm_id,
            User.role.in_([UserRole.firm_owner, UserRole.manager]),
            User.is_active == True,
        )
    ).scalars().all())


def get_users_query(db: Session):
    return db.query(User)


def create_user(db: Session, user_in: UserCreate) -> User:
    hashed_pw = get_password_hash(user_in.password)

    user = User(
        firm_id=user_in.firm_id,
        email=user_in.email,
        hashed_password=hashed_pw,
        full_name=user_in.full_name,
        is_active=user_in.is_active,
        role=user_in.role,
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user: User, user_in: UserUpdate) -> User:
    data = user_in.model_dump(exclude_unset=True)

    if "password" in data:
        user.hashed_password = get_password_hash(data.pop("password"))

    # If the role is being changed, increment token_version.
    # This invalidates all existing JWT sessions for this user,
    # forcing them to log in again with their new permissions.
    if "role" in data and data["role"] != user.role:
        user.token_version = (user.token_version or 0) + 1

    for key, value in data.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user: User) -> None:
    db.delete(user)
    db.commit()