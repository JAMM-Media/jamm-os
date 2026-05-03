"""phase7_billing

Revision ID: 2a0842dc2d3c
Revises: a1b2c3d4e5f6
Create Date: 2026-03-30 04:29:48.719871

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2a0842dc2d3c'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use raw SQL throughout this migration. The test environment runs
    # Base.metadata.create_all() before pytest starts, which may already
    # have created these types and tables. Raw SQL with IF NOT EXISTS / DO
    # blocks handles both a fresh DB and a DB that already has these objects.

    op.execute("""
        DO $$ BEGIN
            CREATE TYPE invoicestatus AS ENUM ('draft', 'sent', 'paid', 'overdue', 'void');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE invoicedeliverymethod AS ENUM ('email', 'portal', 'both');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE stripeconnectionstatus AS ENUM ('connected', 'disconnected', 'error');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id UUID PRIMARY KEY,
            firm_id UUID NOT NULL REFERENCES firms(id) ON DELETE CASCADE,
            client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            engagement_id UUID REFERENCES engagements(id) ON DELETE SET NULL,
            invoice_number VARCHAR(50) NOT NULL,
            line_items JSON,
            subtotal NUMERIC(10,2) NOT NULL,
            tax_rate NUMERIC(5,4) NOT NULL DEFAULT 0.0,
            tax_amount NUMERIC(10,2) NOT NULL DEFAULT 0.0,
            total_amount NUMERIC(10,2) NOT NULL,
            status invoicestatus NOT NULL DEFAULT 'draft',
            due_date DATE,
            paid_at TIMESTAMPTZ,
            sent_at TIMESTAMPTZ,
            notes TEXT,
            notes_client_visible TEXT,
            stripe_payment_intent_id VARCHAR,
            stripe_charge_id VARCHAR,
            delivery_method invoicedeliverymethod NOT NULL DEFAULT 'portal',
            created_by UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
            deleted_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_invoices_firm_id ON invoices (firm_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_invoices_client_id ON invoices (client_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_invoices_status ON invoices (status)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS stripe_connections (
            id UUID PRIMARY KEY,
            firm_id UUID NOT NULL UNIQUE REFERENCES firms(id) ON DELETE CASCADE,
            stripe_account_id VARCHAR NOT NULL,
            status stripeconnectionstatus NOT NULL DEFAULT 'connected',
            stripe_publishable_key VARCHAR,
            country VARCHAR(2),
            default_currency VARCHAR(3),
            charges_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            payouts_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            details_submitted BOOLEAN NOT NULL DEFAULT FALSE,
            connected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            disconnected_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_stripe_connections_firm_id ON stripe_connections (firm_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS time_entries (
            id UUID PRIMARY KEY,
            firm_id UUID NOT NULL REFERENCES firms(id) ON DELETE CASCADE,
            engagement_id UUID NOT NULL REFERENCES engagements(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            invoice_id UUID REFERENCES invoices(id) ON DELETE SET NULL,
            description VARCHAR(500) NOT NULL,
            hours NUMERIC(6,2) NOT NULL,
            hourly_rate NUMERIC(10,2) NOT NULL,
            is_billable BOOLEAN NOT NULL DEFAULT TRUE,
            is_billed BOOLEAN NOT NULL DEFAULT FALSE,
            date DATE NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_time_entries_firm_id ON time_entries (firm_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_time_entries_engagement_id ON time_entries (engagement_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_time_entries_user_id ON time_entries (user_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS time_entries")
    op.execute("DROP TABLE IF EXISTS stripe_connections")
    op.execute("DROP TABLE IF EXISTS invoices")
    op.execute("DROP TYPE IF EXISTS stripeconnectionstatus")
    op.execute("DROP TYPE IF EXISTS invoicedeliverymethod")
    op.execute("DROP TYPE IF EXISTS invoicestatus")
