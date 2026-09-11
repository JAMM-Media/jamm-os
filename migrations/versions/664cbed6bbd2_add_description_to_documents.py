# migrations/versions/664cbed6bbd2_add_description_to_documents.py
"""Add description column to documents

Adds description (nullable Text) to the documents table for optional
human-written subtitles on Firm Library templates and other documents.
Mirrors the exact column definition style of client_note added in Phase 5.

Revision ID: 664cbed6bbd2
Revises: 3fbbc0560976
Create Date: 2026-09-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '664cbed6bbd2'
down_revision: Union[str, Sequence[str], None] = '3fbbc0560976'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('description', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'description')
