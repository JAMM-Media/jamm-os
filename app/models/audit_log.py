# app/models/audit_log.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class AuditLog(Base):
    """
    Centralized, immutable audit log for all significant actions across JAMM PX.

    IRS 4557 requires audit logs be immutable — append-only forever.
    There are NO update or delete operations for this table.
    """

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Nullable: system-generated events have no actor user
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # 'staff', 'client_portal_user', 'system'
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False, default="system")

    # The event name e.g. 'document.downloaded', 'user.login_success'
    action: Mapped[str] = mapped_column(String(200), nullable=False, index=True)

    # e.g. 'document', 'user', 'invoice'
    entity_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # The ID of the record acted upon
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(nullable=True)

    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Any extra context e.g. {'old_role': 'staff', 'new_role': 'manager'}
    # Attribute is named extra_metadata because 'metadata' is reserved by SQLAlchemy.
    extra_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    firm: Mapped["Firm"] = relationship("Firm", back_populates="audit_logs")
    actor: Mapped[Optional["User"]] = relationship("User", foreign_keys=[actor_id])
