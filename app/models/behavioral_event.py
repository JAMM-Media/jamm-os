# app/models/behavioral_event.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class BehavioralEvent(Base):
    __tablename__ = "behavioral_events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id"),
        nullable=False,
        index=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    entity_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        nullable=True,
    )

    actor_type: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        nullable=True,
    )

    # timestamps are application-observed UTC, set Python-side by design
    occurred_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    extra_metadata: Mapped[Optional[dict]] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )

    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        nullable=True,
    )

    request_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        nullable=True,
        index=True,
    )

    __table_args__ = (
        Index(
            "ix_behavioral_events_firm_type_time",
            "firm_id",
            "event_type",
            "occurred_at",
        ),
    )
