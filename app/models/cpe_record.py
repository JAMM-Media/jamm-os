# app/models/cpe_record.py

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class CPERecord(Base):
    __tablename__ = "cpe_records"

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

    reporting_period_start: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    reporting_period_end: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    hours_required: Mapped[Decimal] = mapped_column(
        Numeric(6, 2),
        nullable=False,
    )

    hours_completed: Mapped[Decimal] = mapped_column(
        Numeric(6, 2),
        nullable=False,
        default=0,
        server_default="0",
    )

    deadline: Mapped[Optional[date]] = mapped_column(
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

    firm: Mapped["Firm"] = relationship("Firm", back_populates="cpe_records")
    user: Mapped["User"] = relationship(
        "User",
        back_populates="cpe_records",
        foreign_keys=[user_id],
    )
