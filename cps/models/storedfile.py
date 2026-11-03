from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Index
from .base import Base
import datetime
import uuid


class StoredFile(Base):
    """
    Metadata for a file held in external object storage (AWS S3).
    Only the storage reference lives here - file contents are never stored
    in the database. Book files and covers are kept in two places: the S3
    object (bucket + object_key) and the working copy in the local library
    folder (local_path, relative to the library root).

    entity_type / entity_id / variant link the object to application data:
        book_format   -> books.id,   variant = format (e.g. "EPUB")
        book_cover    -> books.id
        author_image  -> authors.id
        forum_avatar  -> users.id
        upload        -> generic upload via /api/storage (entity optional)
    """
    __tablename__ = 'stored_files'

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_uuid = Column(String(32), nullable=False, unique=True, default=lambda: uuid.uuid4().hex)
    original_filename = Column(String(255), nullable=False)
    object_key = Column(String(1024), nullable=False, unique=True)
    bucket = Column(String(255), nullable=False)
    storage_provider = Column(String(16), nullable=False, default='s3')
    local_path = Column(String(1024))
    category = Column(String(32), nullable=False)
    mime_type = Column(String(255), nullable=False, default='application/octet-stream')
    size_bytes = Column(BigInteger, nullable=False, default=0)
    etag = Column(String(128))
    entity_type = Column(String(32), nullable=False, default='upload')
    entity_id = Column(String(64))
    variant = Column(String(32))
    uploaded_by = Column(Integer, index=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('ix_stored_files_entity', 'entity_type', 'entity_id', 'variant'),
    )

    def to_dict(self):
        """Return a dict safe for JSON responses (no bucket configuration)."""
        return {
            "id": self.file_uuid,
            "original_filename": self.original_filename,
            "category": self.category,
            "mime_type": self.mime_type,
            "size_bytes": self.size_bytes,
            "storage_provider": self.storage_provider,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "variant": self.variant,
            "uploaded_at": self.created_at.isoformat() + "Z" if self.created_at else None,
        }

    def __repr__(self):
        return f'<StoredFile id={self.id} key={self.object_key}>'
