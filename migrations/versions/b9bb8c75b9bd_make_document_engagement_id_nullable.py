# migrations/versions/b9bb8c75b9bd_make_document_engagement_id_nullable.py
"""make_document_engagement_id_nullable

Revision ID: b9bb8c75b9bd
Revises: 7d35737819be
Create Date: 2026-04-30 11:31:45.181811

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9bb8c75b9bd'
down_revision: Union[str, Sequence[str], None] = '7d35737819be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the old CASCADE foreign key and recreate with SET NULL
    op.drop_constraint('documents_engagement_id_fkey', 'documents', type_='foreignkey')
    op.create_foreign_key(
        'documents_engagement_id_fkey',
        'documents', 'engagements',
        ['engagement_id'], ['id'],
        ondelete='SET NULL',
    )
    # Allow NULL on the column
    op.alter_column('documents', 'engagement_id',
                    existing_type=sa.UUID(),
                    nullable=True)


def downgrade() -> None:
    op.alter_column('documents', 'engagement_id',
                    existing_type=sa.UUID(),
                    nullable=False)
    op.drop_constraint('documents_engagement_id_fkey', 'documents', type_='foreignkey')
    op.create_foreign_key(
        'documents_engagement_id_fkey',
        'documents', 'engagements',
        ['engagement_id'], ['id'],
        ondelete='CASCADE',
    )
