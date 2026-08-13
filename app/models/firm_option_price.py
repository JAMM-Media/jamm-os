# app/models/firm_option_price.py

"""One firm's price attached to one system categorical option.

Same null-versus-zero law as firm_tiers:

    price IS NULL  -> unpriced. Routes to quote.
    price = 0.00   -> priced, at zero.

No default, no server_default, for the same reason documented at length in
app/models/firm_tier.py.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


class FirmOptionPrice(Base):
    __tablename__ = "firm_option_prices"

    __table_args__ = (
        UniqueConstraint(
            "firm_id",
            "option_id",
            name="uq_firm_option_prices_firm_option",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    firm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("firms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    option_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("complexity_vocabulary_options.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)

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

    option: Mapped["ComplexityVocabularyOption"] = relationship(
        "ComplexityVocabularyOption"
    )
