"""stored_files.local_path added (local library copy of an S3 object)

Revision ID: e2a9c6b4d8f1
Revises: d7b3e5f1a2c4
Create Date: 2026-11-02 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e2a9c6b4d8f1'
down_revision = 'd7b3e5f1a2c4'
branch_labels = None
depends_on = None


def upgrade():
    existing = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('stored_files')}
    if 'local_path' not in existing:
        with op.batch_alter_table('stored_files', schema=None) as batch_op:
            batch_op.add_column(sa.Column('local_path', sa.String(length=1024), nullable=True))


def downgrade():
    with op.batch_alter_table('stored_files', schema=None) as batch_op:
        batch_op.drop_column('local_path')
