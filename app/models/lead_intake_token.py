# app/models/lead_intake_token.py

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class LeadIntakeToken(Base):
    """
    Short-lived token granting a lead access to continue their intake session.

    Pattern follows the unsubscribe-token model with one deliberate difference:
    this token is NOT single-use. It survives multiple requests across one visit
    and is cleared only on expiry, not on use. This is required because the lead
    may reload or resume partway through a multi-page form.

    The raw token lives transiently only in the emailed link. Only the SHA-256
    hex digest is stored here, following the exact same pattern as
    Enrollment.unsubscribe_token_hash and PortalSession.magic_link_token_hash.

    firm_id and lead_id are derived from this row alone on validation -- the
    request body must never contain either, preventing cross-tenant token reuse.
    """

    __tablename__ = "lead_intake_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    firm_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    lead_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # SHA-256 hex digest (64 chars). Raw token lives only in the emailed link.
    token_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
