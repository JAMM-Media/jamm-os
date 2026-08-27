# app/models/platform_event.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class PlatformEvent(Base):
    """
    Append-only log of events that belong to no firm.

    This table is the SECOND documented exception to the firm_id rule, and it
    also departs from the standard model spine. It carries no firm_id because
    the events it records are network-wide (findings with no owning firm), so
    there is no firm to attribute them to. It has an event_id primary key and
    an occurred_at timestamp, and it has no created_at and no updated_at.

    It mirrors behavioral_events, its sibling, which is the first such
    exception. Everything behavioral_events keeps that makes sense without a
    firm is kept here in the same shape; everything that only makes sense with
    a firm or an actor (firm_id, actor_type, actor_id, session_id, request_id)
    is absent.

    It is written only through log_platform_event() in
    app/services/behavioral_log.py, fire and forget, never inline in a request.
    It has no schemas, no router, and no CRUD.

    Nothing in operational control flow reads this table. The log is a
    recorder, never a gatekeeper: anything the product branches on, gates on,
    or enforces reads durable operational tables instead.

    Ruled Aug 26, 2026 (Ruling 1).
    """

    __tablename__ = "platform_events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
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

    __table_args__ = (
        Index(
            "ix_platform_events_type_time",
            "event_type",
            "occurred_at",
        ),
    )
