# app/models/firm.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Firm(Base):
    """
    The root of the entire multi-tenant system.

    Every piece of data in JAMM OS — every client, every engagement,
    every task, every document — belongs to exactly one Firm.
    A Firm is the accounting business that pays for and uses JAMM OS.

    Think of Firm as a walled container. Data inside one Firm's container
    is completely invisible to every other Firm. This is tenant isolation.
    """

    __tablename__ = "firms"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    # Slug is a URL-safe version of the firm name.
    # Example: "Smith & Associates CPA" → "smith-associates-cpa"
    # Used for public-facing intake form URLs: /intake/{slug}
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    # settings stores firm-level preferences as a JSON blob.
    # Example: {"timezone": "America/New_York", "fiscal_year_start": "01-01"}
    # Using JSON here instead of individual columns lets us add settings
    # later without new migrations for every preference we add.
    settings: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
    )

    # feature_flags controls which features this firm can access.
    # Example: {"esign_enabled": true, "quickbooks_sync": false}
    # This lets us roll out features to specific firms before general release.
    feature_flags: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
    )

    # subscription_tier controls what plan the firm is on.
    # Values: "trial", "starter", "professional", "enterprise"
    # Enforced at the billing layer (Phase 7) — stored here for quick access.
    subscription_tier: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="trial",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
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

    # Relationships — every model that has a firm_id points back here.
    # "cascade all, delete-orphan" means: if a Firm is deleted,
    # all its users/clients/etc are also deleted automatically.
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="firm",
        cascade="all, delete-orphan",
    )

    clients: Mapped[list["Client"]] = relationship(
        "Client",
        back_populates="firm",
        cascade="all, delete-orphan",
    )

    contacts: Mapped[list["Contact"]] = relationship(
        "Contact",
        back_populates="firm",
        cascade="all, delete-orphan",
    )

    engagements: Mapped[list["Engagement"]] = relationship(
        "Engagement",
        back_populates="firm",
        cascade="all, delete-orphan",
    )

    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="firm",
        cascade="all, delete-orphan",
    )

    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="firm",
        cascade="all, delete-orphan",
    )