# app/models/complexity_vocabulary_option.py

"""One selectable option in a categorical dimension's system vocabulary.

System-owned catalog content. NO firm_id, per the August 13, 2026 carve-out
documented in app/models/complexity_flag.py.

These IDs are the canonical option IDs the public config endpoint will later
serve as opaque identifiers, so they are stable and must not be recycled.

Only meaningful for categorical dimensions. As with units, the parent-kind
check needs the parent row and so lives in pricing_config_service, not in a
database constraint.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class ComplexityVocabularyOption(Base):
    __tablename__ = "complexity_vocabulary_options"

    __table_args__ = (
        UniqueConstraint(
            "dimension_id",
            "key",
            name="uq_complexity_vocabulary_options_dimension_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    dimension_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complexity_dimensions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    key: Mapped[str] = mapped_column(String(100), nullable=False)

    # Lead-facing option text.
    label: Mapped[str] = mapped_column(String(200), nullable=False)

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
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

    dimension: Mapped["ComplexityDimension"] = relationship(
        "ComplexityDimension",
        back_populates="vocabulary_options",
    )
