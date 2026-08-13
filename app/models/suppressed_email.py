# app/models/suppressed_email.py

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class SuppressedEmail(Base):
    __tablename__ = "suppressed_emails"

    __table_args__ = (
        UniqueConstraint("firm_id", "email", name="uq_suppressed_email_firm"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Stored lowercased -- normalization happens in the CRUD layer, not here.
    email: Mapped[str] = mapped_column(String(255), nullable=False)

    # Freeform: "unsubscribed", "bounced", etc. "bounced" is not built in this
    # task, but the column exists to avoid a future migration just for the field.
    reason: Mapped[str | None] = mapped_column(String(50), nullable=True)

    suppressed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
