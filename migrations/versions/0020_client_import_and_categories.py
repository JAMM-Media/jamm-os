# migrations/versions/0020_client_import_and_categories.py
"""Add entity_type to clients, category and visibility to documents

Revision ID: 0020_client_import_and_categories
Revises: 0019_transcript_requests
Create Date: 2026-04-15
"""

from alembic import op
import sqlalchemy as sa

revision = "0020_client_import_and_categories"
down_revision = "0019_transcript_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add entity_type to clients
    op.add_column(
        "clients",
        sa.Column("entity_type", sa.String(20), nullable=True),
    )

    # Add category to documents
    op.add_column(
        "documents",
        sa.Column(
            "category",
            sa.String(50),
            nullable=True,
            server_default="other",
        ),
    )

    # Add visibility to documents
    op.add_column(
        "documents",
        sa.Column(
            "visibility",
            sa.String(20),
            nullable=False,
            server_default="internal",
        ),
    )

    # Index category for document library filtering
    op.create_index("ix_documents_category", "documents", ["category"])
    op.create_index("ix_clients_entity_type", "clients", ["entity_type"])


def downgrade() -> None:
    op.drop_index("ix_clients_entity_type", table_name="clients")
    op.drop_index("ix_documents_category", table_name="documents")
    op.drop_column("documents", "visibility")
    op.drop_column("documents", "category")
    op.drop_column("clients", "entity_type")
