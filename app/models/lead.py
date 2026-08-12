# app/models/lead.py

import uuid
from datetime import datetime, timezone
from typing import Optional
import sqlalchemy as sa
from sqlalchemy import String, Boolean, DateTime, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.core.enums import (
    LeadStage,
    LeadLostReason,
    ReferralSource,
    SourcePlatform,
    LeadProvenance,
)


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # NOT unique -- duplicate leads from re-submission or multiple channels
    # are expected and must not be blocked.
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    stage: Mapped[LeadStage] = mapped_column(
        sa.Enum(LeadStage, name="leadstage", native_enum=False),
        nullable=False,
        default=LeadStage.identified,
        server_default="identified",
    )

    lost_reason: Mapped[Optional[LeadLostReason]] = mapped_column(
        sa.Enum(LeadLostReason, name="leadlostreason", native_enum=False),
        nullable=True,
    )

    # Reuses the existing ReferralSource enum verbatim -- same name= as
    # Client.referral_source so attribution flows forward on conversion
    # without translation.
    referral_source: Mapped[Optional[ReferralSource]] = mapped_column(
        sa.Enum(ReferralSource, name="referralsource", native_enum=False),
        nullable=True,
    )

    source_platform: Mapped[Optional[SourcePlatform]] = mapped_column(
        sa.Enum(SourcePlatform, name="sourceplatform", native_enum=False),
        nullable=True,
    )

    # UTM parameters stored verbatim per CRM contract Section 8.
    utm_campaign: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    utm_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    utm_medium: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    utm_content: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    utm_term: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Bare FK only -- no relationship(). Nothing needs to traverse it yet.
    referring_client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Bare FK only -- no relationship(). Nothing needs to traverse it yet.
    referral_partner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("referral_partners.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Set when stage transitions to won. Bare FK only -- no relationship().
    converted_client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Freeform for now. Engagement.engagement_type is a plain String column
    # with no enum class (EFILEABLE_ENGAGEMENT_TYPES is a set, not an Enum).
    # A future alignment opportunity exists once firm service types stabilize
    # into a shared enum.
    service_interest: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Mirrors Client.entity_type's exact convention.
    entity_type: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="individual | business | trust | estate | non_profit",
    )

    revenue_band: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Raw captured answer to the timeline/urgency question. Free text since
    # the exact question wording lives in the not-yet-available nurture tree.
    urgency: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    hot: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    # NO default and NO server_default intentionally. Every creation path
    # must set this explicitly -- precedence correctness depends on it being
    # real every time.
    provenance: Mapped[LeadProvenance] = mapped_column(
        sa.Enum(LeadProvenance, name="leadprovenance", native_enum=False),
        nullable=False,
    )

    # Minutes elapsed from lead creation to first outbound firm response.
    # Computed and set later by a service layer this task does not build.
    first_response_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    firm: Mapped["Firm"] = relationship("Firm", back_populates="leads")
