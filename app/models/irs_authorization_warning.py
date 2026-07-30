# app/models/irs_authorization_warning.py

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class IrsAuthorizationWarning(Base):
    """
    Records an expiry warning that was actually sent for an IRS authorization.

    This table is the control gate for the warning ladder. It replaced the
    boolean expiry_notification_sent column on IrsAuthorization, which could
    only ever express "some warning went out at some point" and therefore
    could not support more than one tier.

    One row per tier per authorization, enforced by a database-level unique
    constraint on (authorization_id, threshold_days) rather than by an
    application check. threshold_days is the tier that fired, expressed as
    days before valid_until, where 0 means the expiry date itself.

    A row is written only after the warning has actually been delivered, so
    the presence of a row is evidence of a send rather than an intent to
    send. Rows for an authorization are deleted when its valid_until changes,
    which resets the ladder for renewals and for corrected typos alike.
    """

    __tablename__ = "irs_authorization_warnings"

    __table_args__ = (
        UniqueConstraint(
            "authorization_id",
            "threshold_days",
            name="uq_irs_auth_warning_auth_threshold",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    authorization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("irs_authorizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The tier that fired, in days before valid_until. 0 is the expiry date.
    threshold_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
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

    # --- Relationships ---
    firm: Mapped["Firm"] = relationship("Firm")
    authorization: Mapped["IrsAuthorization"] = relationship("IrsAuthorization")
