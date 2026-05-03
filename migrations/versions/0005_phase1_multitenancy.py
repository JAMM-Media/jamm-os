"""Phase 1 — Add firms table and firm_id to all core models

This migration:
1. Creates the firms table (the root of multi-tenancy)
2. Adds firm_id to users, clients, contacts, engagements, tasks
3. Adds token_version to users (for session invalidation on role change)
4. Updates the userrole enum with the correct role names

IMPORTANT — Running this on existing data:
If you have existing rows in any of these tables, the migration will fail
because firm_id is NOT NULL but there is no firm to assign them to.

Before running this migration on a database with existing data:
1. Create a "seed" firm manually
2. Update all existing rows to use that firm's ID
3. Then run this migration

For a fresh development database, just run: alembic upgrade head

Revision ID: 0005_phase1_multitenancy
Revises: 0004_user_2fa_fields
Create Date: 2025-01-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# Revision identifiers
revision = "0005_phase1_multitenancy"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Create firms table
    # ------------------------------------------------------------------
    op.create_table(
        "firms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("settings", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("feature_flags", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("subscription_tier", sa.String(50), nullable=False, server_default="trial"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_firms_slug", "firms", ["slug"], unique=True)

    # ------------------------------------------------------------------
    # 2. Update userrole enum to match new role names
    #
    # New roles: firm_owner, manager, staff, client_portal_user, system_admin
    # Old roles (if they existed): admin, staff, client
    #
    # This migration handles two cases:
    # a) userrole enum already exists (upgrade from an older schema) — rename & recreate
    # b) userrole enum does not exist (fresh DB via migrations) — create it and add the column
    # ------------------------------------------------------------------
    conn = op.get_bind()
    userrole_exists = conn.execute(
        sa.text("SELECT EXISTS(SELECT 1 FROM pg_type WHERE typname = 'userrole')")
    ).scalar()
    role_col_exists = conn.execute(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
            "WHERE table_name='users' AND column_name='role')"
        )
    ).scalar()

    if userrole_exists:
        op.execute("ALTER TYPE userrole RENAME TO userrole_old")
        op.execute(
            "CREATE TYPE userrole AS ENUM ('firm_owner', 'manager', 'staff', 'client_portal_user', 'system_admin')"
        )
        if role_col_exists:
            op.execute(
                """
                ALTER TABLE users
                ALTER COLUMN role TYPE userrole
                USING CASE role::text
                    WHEN 'admin'  THEN 'firm_owner'::userrole
                    WHEN 'client' THEN 'client_portal_user'::userrole
                    ELSE role::text::userrole
                END
                """
            )
        op.execute("DROP TYPE userrole_old")
    else:
        op.execute(
            "CREATE TYPE userrole AS ENUM ('firm_owner', 'manager', 'staff', 'client_portal_user', 'system_admin')"
        )

    if not role_col_exists:
        op.add_column(
            "users",
            sa.Column(
                "role",
                sa.Enum(
                    "firm_owner", "manager", "staff", "client_portal_user", "system_admin",
                    name="userrole",
                    create_type=False,
                ),
                nullable=False,
                server_default="staff",
            ),
        )

    # ------------------------------------------------------------------
    # 2b. Add full_name to users (if not present)
    # ------------------------------------------------------------------
    full_name_exists = conn.execute(
        sa.text(
            "SELECT EXISTS(SELECT 1 FROM information_schema.columns "
            "WHERE table_name='users' AND column_name='full_name')"
        )
    ).scalar()
    if not full_name_exists:
        op.add_column(
            "users",
            sa.Column("full_name", sa.String(), nullable=True),
        )

    # ------------------------------------------------------------------
    # 3. Add token_version to users
    # ------------------------------------------------------------------
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )

    # ------------------------------------------------------------------
    # 4. Add firm_id to users
    # ------------------------------------------------------------------
    op.add_column(
        "users",
        sa.Column("firm_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_firm_id",
        "users",
        "firms",
        ["firm_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_users_firm_id", "users", ["firm_id"])
    # After backfilling existing data, run this to enforce NOT NULL:
    # op.alter_column("users", "firm_id", nullable=False)

    # ------------------------------------------------------------------
    # 5. Add firm_id to clients
    # ------------------------------------------------------------------
    op.add_column(
        "clients",
        sa.Column("firm_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_clients_firm_id",
        "clients",
        "firms",
        ["firm_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_clients_firm_id", "clients", ["firm_id"])

    # ------------------------------------------------------------------
    # 6. Add firm_id to contacts
    # ------------------------------------------------------------------
    op.add_column(
        "contacts",
        sa.Column("firm_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_contacts_firm_id",
        "contacts",
        "firms",
        ["firm_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_contacts_firm_id", "contacts", ["firm_id"])

    # ------------------------------------------------------------------
    # 7. Add firm_id to engagements
    # ------------------------------------------------------------------
    op.add_column(
        "engagements",
        sa.Column("firm_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_engagements_firm_id",
        "engagements",
        "firms",
        ["firm_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_engagements_firm_id", "engagements", ["firm_id"])

    # ------------------------------------------------------------------
    # 8. Add firm_id to tasks
    # ------------------------------------------------------------------
    op.add_column(
        "tasks",
        sa.Column("firm_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_tasks_firm_id",
        "tasks",
        "firms",
        ["firm_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_tasks_firm_id", "tasks", ["firm_id"])


def downgrade() -> None:
    # Remove firm_id columns and indexes
    for table in ["tasks", "engagements", "contacts", "clients", "users"]:
        op.drop_constraint(f"fk_{table}_firm_id", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_firm_id", table_name=table)
        op.drop_column(table, "firm_id")

    op.drop_column("users", "token_version")

    # Revert userrole enum
    op.execute("ALTER TYPE userrole RENAME TO userrole_new")
    op.execute("CREATE TYPE userrole AS ENUM ('admin', 'staff', 'client')")
    op.execute(
        """
        ALTER TABLE users
        ALTER COLUMN role TYPE userrole
        USING CASE role::text
            WHEN 'firm_owner'         THEN 'admin'::userrole
            WHEN 'client_portal_user' THEN 'client'::userrole
            ELSE 'staff'::userrole
        END
        """
    )
    op.execute("DROP TYPE userrole_new")

    op.drop_index("ix_firms_slug", table_name="firms")
    op.drop_table("firms")