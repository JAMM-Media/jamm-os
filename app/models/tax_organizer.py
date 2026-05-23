# app/models/tax_organizer.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, JSON, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class TaxOrganizerTemplate(Base):
    """
    A reusable tax organizer template owned by a firm.

    Templates define the structure: a list of sections, each containing
    a list of questions. Three default templates are seeded on firm creation:
    - Individual (1040)
    - Business (1120/1065/1120S)
    - Rental Property

    The `sections` JSON field structure:
    [
        {
            "id": "section_slug",
            "title": "Section Title",
            "description": "Optional helper text shown above section",
            "questions": [
                {
                    "id": "q_slug",
                    "label": "Question text shown to client",
                    "type": "text|number|boolean|select|textarea",
                    "required": true|false,
                    "options": ["opt1", "opt2"]  // only for select type
                }
            ]
        }
    ]
    """

    __tablename__ = "tax_organizer_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # "individual" | "business" | "rental" | "custom"
    organizer_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="custom",
    )

    # JSON array of section objects (see docstring above)
    sections: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    is_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True for the three seeded templates. Firms can still edit them.",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="False for soft-deleted templates.",
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

    firm: Mapped["Firm"] = relationship("Firm")
    organizers: Mapped[list["TaxOrganizer"]] = relationship(
        "TaxOrganizer",
        back_populates="template",
        cascade="all, delete-orphan",
    )


class TaxOrganizer(Base):
    """
    A specific tax organizer instance sent to a client for an engagement.

    Created by staff via POST /tax-organizers/send.
    Client fills it out in the portal.

    The `responses` JSON field mirrors the template's section/question
    structure but stores client-provided answers:
    {
        "section_slug": {
            "q_slug": "client answer value"
        }
    }

    Statuses:
    - sent         — delivered to portal, client has not started
    - in_progress  — client has saved at least one answer
    - submitted    — client has clicked Submit (all required questions answered)
    """

    __tablename__ = "tax_organizers"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

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

    engagement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tax_organizer_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )

    tax_year: Mapped[int] = mapped_column(nullable=False)

    # sent | in_progress | submitted
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="sent",
    )

    # Client's answers — keyed by section_id → question_id → value
    responses: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    # Timestamp when client clicked Submit
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Optional message from staff to client shown at top of organizer
    client_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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

    firm: Mapped["Firm"] = relationship("Firm")
    client: Mapped["Client"] = relationship("Client")
    engagement: Mapped["Engagement"] = relationship("Engagement")
    template: Mapped["TaxOrganizerTemplate"] = relationship(
        "TaxOrganizerTemplate",
        back_populates="organizers",
    )
