# migrations/versions/4d538ddb5404_phase5_add_client_note_to_documents.py
"""Phase 5: add client_note to documents

Adds client_note (nullable Text) to the documents table.
triage_status already exists from the Phase 1 migration (f1e2s3y4s5t6).
This migration touches only the one column needed for portal upload triage.

Revision ID: 4d538ddb5404
Revises: folders0drop0
Create Date: 2026-09-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4d538ddb5404'
down_revision: Union[str, Sequence[str], None] = 'folders0drop0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('documents', sa.Column('client_note', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'client_note')
