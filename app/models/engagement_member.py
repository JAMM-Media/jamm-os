# app/models/engagement_member.py

"""
Engagement membership.

Firm role answers what a person is ALLOWED TO DO. Engagement membership
answers WHOSE WORK a given engagement is. Two independent axes: they
intersect, but neither implies the other. A manager can have broad firm
capability and zero engagements. A staff member promoted to administrator on
one engagement has capability there that exceeds their firm role.

is_administrator is strictly per-engagement and carries nowhere else. Being
an administrator on one engagement means nothing on any other engagement,
and nothing at the firm level.

There is deliberately no minimum-administrator constraint. An engagement
whose only administrator has been deactivated is a Morning Briefing item,
not a blocked operation. firm_owner and manager can always act on any
engagement in the firm without being members of it, which is what makes an
orphaned engagement recoverable rather than stuck.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class EngagementMember(Base):
    __tablename__ = "engagement_members"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # firm_id scopes this membership to one accounting firm. Denormalized from
    # engagement.firm_id on purpose so every membership query can filter on
    # firm_id as its first WHERE clause without joining engagements.
    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    engagement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    is_administrator: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Administrator of THIS engagement only. Never implies any "
                "capability on another engagement or at the firm level.",
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

    __table_args__ = (
        UniqueConstraint("engagement_id", "user_id", name="uq_engagement_member"),
    )

    firm: Mapped["Firm"] = relationship("Firm")
    engagement: Mapped["Engagement"] = relationship("Engagement", back_populates="members")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
