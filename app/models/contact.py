# app/models/contact.py

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # firm_id is required on Contact even though Contact also has a client_id.
    # Why? Because firm_id is our primary tenant isolation key. Every single
    # query in the system filters by firm_id first. Having it directly on
    # Contact means we can filter contacts by firm without a JOIN to clients.
    # This also protects us if a contact ever becomes unlinked from a client.
    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    client_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("clients.id"),
        nullable=True,
    )

    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

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

    firm: Mapped["Firm"] = relationship("Firm", back_populates="contacts")
    client: Mapped["Client"] = relationship("Client", back_populates="contacts", lazy="joined")