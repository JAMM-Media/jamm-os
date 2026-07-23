# app/models/invoice.py

import uuid
from datetime import datetime, date, timezone
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, Date, ForeignKey, Text, Numeric, JSON, Integer, UniqueConstraint, func
from sqlalchemy import Enum as PgEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.core.enums import InvoiceStatus, InvoiceDeliveryMethod


class Invoice(Base):
    __tablename__ = "invoices"

    __table_args__ = (
        UniqueConstraint("firm_id", "invoice_number", name="uq_invoice_firm_invoice_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

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

    engagement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("engagements.id", ondelete="SET NULL"),
        nullable=True,
    )

    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False)

    line_items: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    subtotal: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    tax_rate: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=0.0)
    tax_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0.0)
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    status: Mapped[InvoiceStatus] = mapped_column(
        PgEnum(InvoiceStatus, name="invoicestatus"),
        default=InvoiceStatus.draft,
        nullable=False,
        index=True,
    )

    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    reminder_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    last_reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes_client_visible: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    stripe_payment_intent_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    stripe_charge_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    amount_paid: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    refunded_amount: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    refund_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    delivery_method: Mapped[InvoiceDeliveryMethod] = mapped_column(
        PgEnum(InvoiceDeliveryMethod, name="invoicedeliverymethod"),
        default=InvoiceDeliveryMethod.portal,
        nullable=False,
    )

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    firm: Mapped["Firm"] = relationship("Firm", back_populates="invoices")
    client: Mapped["Client"] = relationship("Client", back_populates="invoices")
    engagement: Mapped[Optional["Engagement"]] = relationship("Engagement", back_populates="invoices")
    creator: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])
    time_entries: Mapped[list["TimeEntry"]] = relationship("TimeEntry", back_populates="invoice")
