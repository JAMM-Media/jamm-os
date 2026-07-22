# app/models/checklist_template.py

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, JSON, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class ChecklistTemplate(Base):
    """
    A reusable checklist that staff can apply when creating a new DocumentRequest.

    Instead of manually building the same checklist items for every tax return
    or audit engagement, a firm creates templates once and stamps them onto new
    requests. Templates are scoped to a firm and optionally tied to a specific
    engagement type (e.g. "1040 Individual", "S-Corp Review").

    items is a JSON array of objects, each with the shape:
        {
            "id":          "<uuid string>",
            "label":       "2023 W-2",
            "description": "Your W-2 from your primary employer.",
            "is_required": true,
            "status":      "pending"   # pending | uploaded | approved | rejected
        }
    The status field on template items is always "pending" — it represents
    the default state stamped onto a new DocumentRequest, not a live status.
    """

    __tablename__ = "checklist_templates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Tenant isolation — templates belong to one firm and are invisible to others.
    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Display name for the template, e.g. "Individual Tax Return (1040)".
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Optional engagement type this template is designed for.
    # Stored as a string so the model stays decoupled from the EngagementType
    # enum — the enum is enforced at the API/schema layer, not here.
    # Example values: "individual_tax", "business_tax", "audit", "bookkeeping"
    engagement_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Template checklist items. Same structure as DocumentRequest.checklist_items.
    # When a staff member applies this template to a new DocumentRequest, these
    # items are deep-copied into the request's checklist_items field.
    items: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    firm: Mapped["Firm"] = relationship("Firm", back_populates="checklist_templates")
