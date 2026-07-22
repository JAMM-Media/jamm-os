# app/models/stripe_connection.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, ForeignKey, func
from sqlalchemy import Enum as PgEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.core.enums import StripeConnectionStatus


class StripeConnection(Base):
    __tablename__ = "stripe_connections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    stripe_account_id: Mapped[str] = mapped_column(String, nullable=False)

    status: Mapped[StripeConnectionStatus] = mapped_column(
        PgEnum(StripeConnectionStatus, name="stripeconnectionstatus"),
        default=StripeConnectionStatus.connected,
        nullable=False,
    )

    stripe_publishable_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    default_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)

    charges_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payouts_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    details_submitted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    disconnected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    firm: Mapped["Firm"] = relationship("Firm", back_populates="stripe_connection")
