"""add task_file_links table

Revision ID: 375e6bdc8287
Revises: 0fd727d17cb2
Create Date: 2026-09-16 11:52:21.717767

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '375e6bdc8287'
down_revision: Union[str, Sequence[str], None] = '0fd727d17cb2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'task_file_links',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('firm_id', sa.Uuid(), nullable=False),
        sa.Column('task_id', sa.Uuid(), nullable=False),
        sa.Column('document_id', sa.Uuid(), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['firm_id'], ['firms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_id', 'document_id', name='uq_task_file_link'),
    )
    op.create_index(op.f('ix_task_file_links_created_by'), 'task_file_links', ['created_by'], unique=False)
    op.create_index(op.f('ix_task_file_links_document_id'), 'task_file_links', ['document_id'], unique=False)
    op.create_index(op.f('ix_task_file_links_firm_id'), 'task_file_links', ['firm_id'], unique=False)
    op.create_index(op.f('ix_task_file_links_task_id'), 'task_file_links', ['task_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_task_file_links_task_id'), table_name='task_file_links')
    op.drop_index(op.f('ix_task_file_links_firm_id'), table_name='task_file_links')
    op.drop_index(op.f('ix_task_file_links_document_id'), table_name='task_file_links')
    op.drop_index(op.f('ix_task_file_links_created_by'), table_name='task_file_links')
    op.drop_table('task_file_links')
