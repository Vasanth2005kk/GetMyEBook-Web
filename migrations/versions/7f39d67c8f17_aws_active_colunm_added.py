"""aws active colunm added

Revision ID: 7f39d67c8f17
Revises: 04f7fd038b41
Create Date: 2026-06-11 14:41:05.772656

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '7f39d67c8f17'
down_revision = '04f7fd038b41'
branch_labels = None
depends_on = None


def upgrade():
    # Only add the three new AWS toggle columns to the settings table.
    # The forum tables are managed separately and must NOT be touched here.
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('aws_active', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('aws_enabled_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('aws_disabled_at', sa.DateTime(), nullable=True))


def downgrade():
    # Remove only the three AWS toggle columns added by this migration.
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.drop_column('aws_disabled_at')
        batch_op.drop_column('aws_enabled_at')
        batch_op.drop_column('aws_active')
