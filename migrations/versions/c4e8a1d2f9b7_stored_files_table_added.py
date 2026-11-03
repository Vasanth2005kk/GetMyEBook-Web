"""stored_files table added (AWS S3 file metadata)

Revision ID: c4e8a1d2f9b7
Revises: b56035907125
Create Date: 2026-11-02 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4e8a1d2f9b7'
down_revision = 'b56035907125'
branch_labels = None
depends_on = None


def upgrade():
    # The application also runs Base.metadata.create_all() on startup, so the
    # table may already exist when this migration is applied.
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('stored_files'):
        op.create_table('stored_files',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('file_uuid', sa.String(length=32), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('object_key', sa.String(length=1024), nullable=False),
        sa.Column('bucket', sa.String(length=255), nullable=False),
        sa.Column('storage_provider', sa.String(length=16), nullable=False),
        sa.Column('category', sa.String(length=32), nullable=False),
        sa.Column('mime_type', sa.String(length=255), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('etag', sa.String(length=128), nullable=True),
        sa.Column('entity_type', sa.String(length=32), nullable=False),
        sa.Column('entity_id', sa.String(length=64), nullable=True),
        sa.Column('variant', sa.String(length=32), nullable=True),
        sa.Column('uploaded_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('file_uuid'),
        sa.UniqueConstraint('object_key')
        )
    existing = {ix['name'] for ix in sa.inspect(op.get_bind()).get_indexes('stored_files')}
    with op.batch_alter_table('stored_files', schema=None) as batch_op:
        if 'ix_stored_files_entity' not in existing:
            batch_op.create_index('ix_stored_files_entity', ['entity_type', 'entity_id', 'variant'], unique=False)
        if 'ix_stored_files_uploaded_by' not in existing:
            batch_op.create_index(batch_op.f('ix_stored_files_uploaded_by'), ['uploaded_by'], unique=False)


def downgrade():
    with op.batch_alter_table('stored_files', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_stored_files_uploaded_by'))
        batch_op.drop_index('ix_stored_files_entity')

    op.drop_table('stored_files')
