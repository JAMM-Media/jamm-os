# app/models/staff_credential.py

import uuid
from datetime import date, datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import String, Date, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.core.enums import CredentialType


class StaffCredential(Base):
    __tablename__ = "staff_credentials"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    credential_type: Mapped[CredentialType] = mapped_column(
        sa.Enum(CredentialType, native_enum=False),
        nullable=False,
    )

    credential_number: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    state: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    issued_at: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )

    expires_at: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
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

    firm: Mapped["Firm"] = relationship("Firm", back_populates="staff_credentials")
    user: Mapped["User"] = relationship(
        "User",
        back_populates="staff_credentials",
        foreign_keys=[user_id],
    )
