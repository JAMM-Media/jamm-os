# app/models/firm_option_price.py

"""One firm's price attached to one system categorical option, in one scope.

Same null-versus-zero law as firm_tiers:

    price IS NULL  -> unpriced. Routes to quote.
    price = 0.00   -> priced, at zero.

No default, no server_default, for the same reason documented at length in
app/models/firm_tier.py.

SCOPE, added August 17, 2026. Before this, an option price was keyed
(firm_id, option_id) alone, which meant a firm had exactly one price per
vocabulary option no matter how many engagement types it offered. That made
per-engagement-type overrides expressible for numeric dimensions (tiers hang
off config_id, so they scope naturally) and inexpressible for categorical ones:
a scoped config tree and the blanket tree both read the same price row. A firm
could not say "staking is 300 on a 1040 and 500 on an 1120".

service_catalog_entry_id closes that. NULL means blanket, non-NULL means the
price applies only when pricing that engagement type, matching
firm_dimension_configs exactly. Resolution reads the scoped price when one
exists for the engagement type being priced and the blanket price otherwise;
it is wholesale replacement per option, never a merge.
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
        # One price per firm per option PER SCOPE.
        #
        # postgresql_nulls_not_distinct is load-bearing here for the same
        # reason it is on firm_dimension_configs. service_catalog_entry_id is
        # the only nullable member, and NULL is the blanket case, which is the
        # common case. Under Postgres default NULLS DISTINCT two blanket prices
        # for the same option would both read as (firm, option, NULL) and BOTH
        # insert cleanly, because NULL never equals NULL, silently
        # un-enforcing this constraint exactly where it matters most.
        UniqueConstraint(
            "firm_id",
            "option_id",
            "service_catalog_entry_id",
            name="uq_firm_option_prices_firm_option",
            postgresql_nulls_not_distinct=True,
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

    # NULL means blanket, non-NULL means this price applies only when pricing
    # that engagement type. See the module docstring.
    #
    # CASCADE rather than SET NULL, matching firm_dimension_configs: deleting a
    # catalog entry deletes the thing this price exists for. SET NULL would
    # promote a per-engagement price to the blanket price for every engagement
    # type, which is a mispricing rather than a cleanup, and it could also
    # collide with an existing blanket row.
    service_catalog_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey(
            "service_catalog_entries.id",
            ondelete="CASCADE",
            name="fk_firm_option_prices_service_catalog_entry",
        ),
        nullable=True,
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
