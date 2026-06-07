# app/models/firm.py

import uuid
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import String, Boolean, DateTime, Text, JSON, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.core.enums import StaffAuthPolicy


class Firm(Base):
    """
    The root of the entire multi-tenant system.

    Every piece of data in JAMM PX — every client, every engagement,
    every task, every document — belongs to exactly one Firm.
    A Firm is the accounting business that pays for and uses JAMM PX.

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

    staff_auth_policy: Mapped[str] = mapped_column(
        sa.String,
        nullable=False,
        default=StaffAuthPolicy.EITHER.value,
    )

    plan_override: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    index_consent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
        comment="Firm has consented to contribute anonymized data to the JAMM Intelligence Index.",
    )

    timesheet_approval_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    concierge_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')
    firm_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    concierge_onboarded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default='false')

    sending_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sending_domain_postmark_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sending_domain_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    sending_domain_dkim_host: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sending_domain_dkim_value: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    sending_domain_return_path_host: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    sending_domain_return_path_value: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    portal_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    portal_domain_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    portal_domain_verification_token: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    staff_calendar_colors: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
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

    briefing_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships -- every model that has a firm_id points back here.
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

    document_requests: Mapped[list["DocumentRequest"]] = relationship(
        "DocumentRequest",
        back_populates="firm",
        cascade="all, delete-orphan",
    )

    checklist_templates: Mapped[list["ChecklistTemplate"]] = relationship(
        "ChecklistTemplate",
        back_populates="firm",
        cascade="all, delete-orphan",
    )

    signature_envelopes: Mapped[list["SignatureEnvelope"]] = relationship(
        "SignatureEnvelope",
        back_populates="firm",
        cascade="all, delete-orphan",
    )

    engagement_letter_templates: Mapped[list["EngagementLetterTemplate"]] = relationship(
        "EngagementLetterTemplate",
        back_populates="firm",
        cascade="all, delete-orphan",
    )

    portal_sessions: Mapped[list["PortalSession"]] = relationship(
        "PortalSession",
        back_populates="firm",
        cascade="all, delete-orphan",
    )

    portal_notifications: Mapped[list["PortalNotification"]] = relationship(
        "PortalNotification",
        back_populates="firm",
        cascade="all, delete-orphan",
    )

    invoices: Mapped[list["Invoice"]] = relationship("Invoice", back_populates="firm")
    time_entries: Mapped[list["TimeEntry"]] = relationship("TimeEntry", back_populates="firm")

    stripe_connection: Mapped[Optional["StripeConnection"]] = relationship(
        "StripeConnection",
        back_populates="firm",
        uselist=False,
    )

    integrations: Mapped[list["Integration"]] = relationship(
        "Integration",
        back_populates="firm",
        cascade="all, delete-orphan",
    )

    automation_rules: Mapped[list["AutomationRule"]] = relationship(
        "AutomationRule", back_populates="firm", cascade="all, delete-orphan"
    )

    notifications: Mapped[list["Notification"]] = relationship(
        "Notification",
        back_populates="firm",
        cascade="all, delete-orphan",
    )

    notification_preferences: Mapped[list["NotificationPreference"]] = relationship(
        "NotificationPreference",
        back_populates="firm",
        cascade="all, delete-orphan",
    )

    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="firm",
        cascade="all, delete-orphan",
    )

    retention_policy: Mapped[Optional["DataRetentionPolicy"]] = relationship(
        "DataRetentionPolicy",
        back_populates="firm",
        uselist=False,
        cascade="all, delete-orphan",
    )

    engagement_templates: Mapped[list["EngagementTemplate"]] = relationship(
        "EngagementTemplate",
        back_populates="firm",
        cascade="all, delete-orphan",
    )