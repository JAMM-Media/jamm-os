# app/models/integration.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Text, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Integration(Base):
    """
    Stores one OAuth integration record per firm per provider.
    Tokens are stored encrypted — never plaintext.
    """

    __tablename__ = "integrations"

    __table_args__ = (
        UniqueConstraint("firm_id", "provider", name="uq_integration_firm_provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    firm_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # e.g. "quickbooks", "google_calendar", "outlook"
    provider: Mapped[str] = mapped_column(String(100), nullable=False)

    # "connected", "disconnected", "error"
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="disconnected")

    encrypted_access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    encrypted_refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    token_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Comma-separated scope strings
    scopes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # QB realm ID, or calendar account email
    external_account_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    connected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )

    firm: Mapped["Firm"] = relationship("Firm", back_populates="integrations")
