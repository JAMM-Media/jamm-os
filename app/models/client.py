# app/models/client.py

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # firm_id scopes this client to exactly one accounting firm.
    # A client record for "John Smith" at Firm A is completely separate
    # from a client record for "John Smith" at Firm B — even if it's the
    # same real person. This is intentional: each firm manages their own
    # client list independently.
    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50))

    company_name: Mapped[str | None] = mapped_column(String(200))
    tax_id: Mapped[str | None] = mapped_column(String(100))

    address_line1: Mapped[str | None] = mapped_column(String(200))
    address_line2: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(100))
    state: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str | None] = mapped_column(String(100))

    tags: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(String(2000))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationship back to the Firm that owns this client.
    firm: Mapped["Firm"] = relationship("Firm", back_populates="clients")

    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="client",
        cascade="all, delete-orphan",
    )

    engagements: Mapped[list["Engagement"]] = relationship(
        "Engagement",
        back_populates="client",
        cascade="all, delete-orphan",
    )

    contacts: Mapped[list["Contact"]] = relationship(
        "Contact",
        back_populates="client",
        cascade="all, delete-orphan",
    )

    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="client",
        cascade="all, delete-orphan",
    )