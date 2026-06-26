# app/models/user.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, DateTime, Boolean, Text, Integer, ForeignKey, Numeric
from sqlalchemy import Enum as PgEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.core.enums import UserRole


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    # firm_id links this user to exactly one Firm.
    # Every user belongs to a firm. There are no "global" users except
    # system_admin, which is handled separately at the application layer.
    # nullable=False means you cannot create a user without assigning them
    # to a firm — this enforces tenant isolation at the database level.
    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    email: Mapped[str] = mapped_column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )

    hashed_password: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )

    full_name: Mapped[Optional[str]] = mapped_column(
        String,
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        default=True,
    )

    role: Mapped[UserRole] = mapped_column(
        PgEnum(UserRole, name="userrole"),
        default=UserRole.staff,
        nullable=False,
    )

    cost_rate: Mapped[Optional[float]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        default=None,
    )

    # token_version is used for session invalidation.
    # When a user's role changes, we increment this number.
    # Every JWT we issue includes this number. When the token is validated,
    # we check that the number in the token matches the current number in the DB.
    # If they don't match, the token is rejected — forcing a fresh login.
    # This means: change someone's role → their existing sessions immediately stop working.
    token_version: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # 2FA fields — scaffolded now, enforced in Phase 11 compliance hardening.
    totp_secret: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        default=None,
    )

    totp_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    backup_codes_hash: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )

    password_reset_token_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        default=None,
    )

    password_reset_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    magic_link_token_hash: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        default=None,
    )

    magic_link_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    failed_login_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        server_default="0",
    )

    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    staff_refresh_token_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    staff_refresh_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    calendar_settings: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationship back to the firm this user belongs to.
    firm: Mapped["Firm"] = relationship("Firm", back_populates="users")

    time_entries: Mapped[list["TimeEntry"]] = relationship(
        "TimeEntry",
        back_populates="user",
        foreign_keys="[TimeEntry.user_id]",
        primaryjoin="User.id == TimeEntry.user_id",
    )

    staff_credentials: Mapped[list["StaffCredential"]] = relationship(
        "StaffCredential",
        back_populates="user",
        foreign_keys="[StaffCredential.user_id]",
        cascade="all, delete-orphan",
    )

    cpe_records: Mapped[list["CPERecord"]] = relationship(
        "CPERecord",
        back_populates="user",
        foreign_keys="[CPERecord.user_id]",
        cascade="all, delete-orphan",
    )