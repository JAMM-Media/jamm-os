# migrations/versions/0044_add_entity_subtype_to_clients.py

from alembic import op
import sqlalchemy as sa

revision = '0044_add_entity_subtype_to_clients'
down_revision = '0043_user_login_lockout_fields'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('clients', sa.Column(
        'entity_subtype',
        sa.String(50),
        nullable=True,
        comment='sole_proprietor | partnership | llc | s_corp | c_corp | professional_corp | revocable_trust | irrevocable_trust | charitable_trust | special_needs_trust | public_charity | private_foundation | social_welfare | other_tax_exempt'
    ))


def downgrade():
    op.drop_column('clients', 'entity_subtype')
