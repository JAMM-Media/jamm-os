# app/models/complexity_dimension.py

"""One dimension of complexity under a system flag.

System-owned catalog content. NO firm_id, per the August 13, 2026 carve-out
documented in app/models/complexity_flag.py.

The system catalog owns hierarchy order through hierarchy_rank. Firms only
choose whether to link a dimension under a coarser one; they never reorder the
hierarchy itself.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import DimensionKind, DimensionRole
from app.db.base_class import Base


class ComplexityDimension(Base):
    __tablename__ = "complexity_dimensions"

    __table_args__ = (
        UniqueConstraint(
            "flag_id",
            "key",
            name="uq_complexity_dimensions_flag_key",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    flag_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complexity_flags.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Unique within the flag, not globally: two flags may both have a
    # "transaction_volume" dimension and they are different dimensions.
    key: Mapped[str] = mapped_column(String(100), nullable=False)

    kind: Mapped[DimensionKind] = mapped_column(
        sa.Enum(DimensionKind, name="dimensionkind", native_enum=False),
        nullable=False,
    )

    # The content session fills this. Nullable now so the schema layer does not
    # wait on content.
    question_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Coarse to fine ordering within the flag. Lower rank is coarser and can
    # only ever be a parent, never a child, of a higher rank. This is what the
    # downhill-only linking rule in pricing_config_service reads.
    hierarchy_rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    # False marks a dimension that never participates in dependency chains,
    # in either direction.
    linkable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )

    # Recommended default per the build reference; the content session fills it.
    # Nullable because a recommendation is not required for the dimension to exist.
    default_role: Mapped[Optional[DimensionRole]] = mapped_column(
        sa.Enum(DimensionRole, name="dimensionrole", native_enum=False),
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

    flag: Mapped["ComplexityFlag"] = relationship(
        "ComplexityFlag",
        back_populates="dimensions",
    )

    units: Mapped[list["ComplexityDimensionUnit"]] = relationship(
        "ComplexityDimensionUnit",
        back_populates="dimension",
        cascade="all, delete-orphan",
    )

    vocabulary_options: Mapped[list["ComplexityVocabularyOption"]] = relationship(
        "ComplexityVocabularyOption",
        back_populates="dimension",
        cascade="all, delete-orphan",
    )
