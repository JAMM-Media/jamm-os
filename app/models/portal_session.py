# app/models/portal_session.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class PortalSession(Base):
    """
    Tracks active client portal sessions.

    Each login creates one record. The refresh_token_hash is a SHA-256 hash
    of the issued refresh token (never stored plaintext). The access_jti is
    the JWT ID of the current active access token — used to invalidate it
    without waiting for expiry.
    """

    __tablename__ = "portal_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # SHA-256 hash of the refresh token — high-entropy random string, so SHA-256 is sufficient.
    refresh_token_hash: Mapped[str] = mapped_column(String, nullable=False)

    # JWT ID of the current active access token — used for per-token invalidation.
    access_jti: Mapped[str] = mapped_column(String, nullable=False)

    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Hard expiry — session cannot be renewed past this point regardless of activity.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # "system", "firm_owner", or "client"
    revoked_by: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    magic_link_token_hash: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    magic_link_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Relationships ---
    firm: Mapped["Firm"] = relationship("Firm", back_populates="portal_sessions")
    client: Mapped["Client"] = relationship("Client", back_populates="portal_sessions")
