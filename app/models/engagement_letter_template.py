# app/models/engagement_letter_template.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class EngagementLetterTemplate(Base):
    """
    A reusable HTML template for generating engagement letters.

    Templates belong to a Firm and can optionally be scoped to a specific
    engagement type. The body_html field contains merge tags (e.g. {{client_name}})
    that are substituted at render time; variable_fields lists which tags are
    present so the UI can prompt the user to supply values before sending.
    """

    __tablename__ = "engagement_letter_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Human-readable template name shown in dropdowns.
    # Example: "Individual Tax Return Engagement Letter"
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # Optional filter so templates can be pre-selected for a given engagement type.
    # Example: "tax_return", "bookkeeping", "audit"
    # If None, the template appears for all engagement types.
    engagement_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Full rich-text HTML body with merge tags, e.g. {{client_name}}, {{fee_amount}}.
    body_html: Mapped[str] = mapped_column(Text, nullable=False)

    # List of merge field names present in body_html.
    # Example: ["client_name", "fee_amount", "engagement_date"]
    # Stored separately so the UI can enumerate required fields without parsing the HTML.
    variable_fields: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

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

    firm: Mapped["Firm"] = relationship(
        "Firm",
        back_populates="engagement_letter_templates",
    )
