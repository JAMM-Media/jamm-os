# app/models/complexity_flag_engagement_type.py

"""Which engagement types a system complexity flag applies to.

System-owned catalog content. NO firm_id, per the August 13, 2026 carve-out
documented in app/models/complexity_flag.py.

engagement_type is stored as a plain String(50) rather than a native enum,
matching how Engagement.engagement_type is stored everywhere else in this
codebase. Validation that the value is a real EngagementType member happens at
the schema layer (app/schemas/complexity_catalog.py).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class ComplexityFlagEngagementType(Base):
    __tablename__ = "complexity_flag_engagement_types"

    __table_args__ = (
        UniqueConstraint(
            "flag_id",
            "engagement_type",
            name="uq_complexity_flag_engagement_types_flag_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    flag_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complexity_flags.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    engagement_type: Mapped[str] = mapped_column(String(50), nullable=False)

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

    flag: Mapped["ComplexityFlag"] = relationship(
        "ComplexityFlag",
        back_populates="engagement_types",
    )
