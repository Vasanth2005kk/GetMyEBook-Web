"""aws_active toggle columns re-added to settings

Revision ID: d7b3e5f1a2c4
Revises: c4e8a1d2f9b7
Create Date: 2026-11-02 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd7b3e5f1a2c4'
down_revision = 'c4e8a1d2f9b7'
branch_labels = None
depends_on = None

_COLUMNS = (
    ('aws_active', sa.Boolean()),
    ('aws_enabled_at', sa.DateTime()),
    ('aws_disabled_at', sa.DateTime()),
)


def upgrade():
    # Columns may already exist if the application created them on startup
    existing = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('settings')}
    with op.batch_alter_table('settings', schema=None) as batch_op:
        for name, type_ in _COLUMNS:
            if name not in existing:
                batch_op.add_column(sa.Column(name, type_, nullable=True))


def downgrade():
    with op.batch_alter_table('settings', schema=None) as batch_op:
        for name, _ in reversed(_COLUMNS):
            batch_op.drop_column(name)
