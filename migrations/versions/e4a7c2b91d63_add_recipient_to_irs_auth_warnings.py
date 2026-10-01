# migrations/versions/e4a7c2b91d63_add_recipient_to_irs_auth_warnings.py
"""record IRS expiry warning recipients one row per recipient per tier

Revision ID: e4a7c2b91d63
Revises: b66b4394a869
Create Date: 2026-09-24 00:00:00.000000

Repointed twice, and the reason is the same both times: this revision kept
waiting to be pushed while the chain grew past its parent.

  Oct 1, 2026: from a4d91c7b3e28 to 1dbec4aebadd, after Ben's
  9703bc76ace7, 1cdc9c33705a and 1dbec4aebadd forked from a4d91c7b3e28.
  Oct 11, 2026: from 1dbec4aebadd to b66b4394a869, after Ben's calendar
  pair 0310a1b5d296 and b66b4394a869 forked from 1dbec4aebadd, which is
  the revision the first repoint had just landed on.

Fifth stale parent in three weeks. Both times alembic reported two heads
and both times this revision rebased onto the end of the other chain rather
than merging, because it only touches irs_authorization_warnings and none
of those five revisions does.

Hand-written, because the downgrade is destructive and autogenerate cannot
write a data-preserving one.

Ruled Sep 22 and Sep 24, 2026. irs_authorization_warnings held one row per
(authorization_id, threshold_days) and no record of who the warning reached,
so a compliance question about who was told could only be answered by
re-resolving current firm membership, which answers who would be warned today
while appearing to answer who was warned then. It now holds one row per
recipient per tier. The fired-once check becomes "any row exists for this
tier".

recipient_user_id is nullable and its foreign key is ON DELETE SET NULL. Users
are hard-deleted in this codebase, so a cascade would delete the receipt along
with the person, and NOT NULL would make the delete fail outright. Keeping the
row with a null recipient preserves the fact that the tier fired.

The new unique constraint uses Postgres' default NULLS DISTINCT, deliberately,
and postgresql_nulls_not_distinct is NOT passed. Two kinds of null-recipient
row have to be able to coexist on one tier: rows written before this migration,
which are never backfilled, and rows nulled later by user deletion. Under NULLS
NOT DISTINCT the second deletion on a shared tier would raise a unique
violation and block an unrelated user delete.

DOWNGRADE IS LOSSY, and irreversibly so. The old constraint permits one row per
(authorization_id, threshold_days), so every extra recipient's row must be
deleted to recreate it. The downgrade keeps the earliest sent_at per tier, with
id as the tiebreak, and discards the rest. Re-upgrading restores the schema but
not the deleted receipts. The permanent record of who was warned is the
irs_authorization.expiry_warning_sent behavioral event, which carries
recipient_user_ids and emailed_user_ids and is append-only; that dual write is
why this table can afford a lossy downgrade at all.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4a7c2b91d63"
down_revision: Union[str, Sequence[str], None] = "b66b4394a869"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLE = "irs_authorization_warnings"

RECIPIENT_COMMENT = (
    "User who received this tier in-app. NULL for rows written before "
    "Sep 24, 2026 or after the user was deleted."
)

OLD_CONSTRAINT = "uq_irs_auth_warning_auth_threshold"
NEW_CONSTRAINT = "uq_irs_auth_warning_auth_threshold_recipient"
RECIPIENT_FK = "fk_irs_auth_warning_recipient_user"
RECIPIENT_INDEX = "ix_irs_authorization_warnings_recipient_user_id"


def upgrade() -> None:
    op.add_column(
        TABLE,
        sa.Column(
            "recipient_user_id",
            sa.UUID(),
            nullable=True,
            comment=RECIPIENT_COMMENT,
        ),
    )

    # Named explicitly and created after the column exists, never inline, so
    # the live catalog can be asked whether it landed.
    op.create_foreign_key(
        RECIPIENT_FK,
        TABLE,
        "users",
        ["recipient_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(RECIPIENT_INDEX, TABLE, ["recipient_user_id"])

    op.drop_constraint(OLD_CONSTRAINT, TABLE, type_="unique")

    # No postgresql_nulls_not_distinct here. The default, NULLS DISTINCT, is
    # the ruling: several null-recipient rows on one tier must coexist.
    op.create_unique_constraint(
        NEW_CONSTRAINT,
        TABLE,
        ["authorization_id", "threshold_days", "recipient_user_id"],
    )


def downgrade() -> None:
    # Lossy by construction: the old constraint cannot be recreated while more
    # than one row exists per tier. Earliest sent_at survives, id breaks ties
    # so the choice is deterministic rather than whatever the planner returns.
    op.execute(
        """
        DELETE FROM irs_authorization_warnings AS a
        USING irs_authorization_warnings AS b
        WHERE a.authorization_id = b.authorization_id
          AND a.threshold_days = b.threshold_days
          AND (a.sent_at, a.id) > (b.sent_at, b.id)
        """
    )

    op.drop_constraint(NEW_CONSTRAINT, TABLE, type_="unique")

    op.create_unique_constraint(
        OLD_CONSTRAINT,
        TABLE,
        ["authorization_id", "threshold_days"],
    )

    op.drop_index(RECIPIENT_INDEX, table_name=TABLE)
    op.drop_constraint(RECIPIENT_FK, TABLE, type_="foreignkey")
    op.drop_column(TABLE, "recipient_user_id")
