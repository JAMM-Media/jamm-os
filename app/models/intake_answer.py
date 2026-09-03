# app/models/intake_answer.py

import uuid
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class IntakeAnswer(Base):
    """
    Append-only record of every answer submitted during public intake.

    Kind rules:
      flag                  -- no dimension_key, no value_* (the flag being set IS the answer)
      dimension_numeric     -- dimension_key required, value_numeric set
      dimension_categorical -- dimension_key required, value_option_id required, value_text for Other
      dimension_boolean     -- dimension_key required, value_boolean set

    value_text is nullable and used only when a categorical answer selects an
    "Other" option that requires free-text clarification; it is null for all
    other kinds.

    No updated_at: this table is append-only by design. Nothing may update a
    row; a corrected answer is a new row.
    """

    __tablename__ = "intake_answers"

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

    kind: Mapped[str] = mapped_column(
        sa.Enum(
            "flag",
            "dimension_numeric",
            "dimension_categorical",
            "dimension_boolean",
            name="intakeanswerkind",
            native_enum=False,
        ),
        nullable=False,
    )

    # Null only for kind='flag'. All dimension kinds must populate this.
    dimension_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Categorical only. The UUID of the selected option in the pricing catalog.
    # Stored without a FK constraint -- the option lives in the pricing catalog
    # which this table does not own. dimension_key is stored alongside so no
    # row requires a join to be understood.
    value_option_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )

    # dimension_numeric only
    value_numeric: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)

    # dimension_boolean only
    value_boolean: Mapped[Optional[bool]] = mapped_column(nullable=True)

    # Categorical "Other" free text. Null for all non-categorical answers and
    # for categorical answers that select a standard (non-Other) option.
    value_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Append-only -- no updated_at column.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
