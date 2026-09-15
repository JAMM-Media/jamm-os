"""cascade_delete_document_folders_on_engagement_delete

Folders are structure that belongs to an engagement; they should delete
with it. The previous ON DELETE SET NULL on engagement_id caused a
CheckViolation: SET NULL fired, then the CHECK constraint
ck_document_folders_scope_fk_consistency refused scope='engagement'
with a NULL engagement_id. Documents (content) are guarded by a
separate attachment check in delete_engagement that already runs first.

Revision ID: 4f66ab6bde66
Revises: 4742add_document_request_templates
Create Date: 2026-09-14 18:41:37.028604

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '4f66ab6bde66'
down_revision: Union[str, Sequence[str], None] = '4742add_document_request_templates'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('document_folders_engagement_id_fkey', 'document_folders', type_='foreignkey')
    op.create_foreign_key(
        'fk_document_folders_engagement_id_engagements',
        'document_folders', 'engagements',
        ['engagement_id'], ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint('fk_document_folders_engagement_id_engagements', 'document_folders', type_='foreignkey')
    op.create_foreign_key(
        'document_folders_engagement_id_fkey',
        'document_folders', 'engagements',
        ['engagement_id'], ['id'],
        ondelete='SET NULL',
    )
