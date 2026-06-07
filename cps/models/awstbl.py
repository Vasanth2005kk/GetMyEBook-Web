from sqlalchemy import Column, Integer, String, Text, DateTime
from .base import Base
import datetime


class AWSCredentials(Base):
    """
    Stores encrypted AWS credentials for S3 integration.
    Sensitive fields (aws_access_key_id, aws_secret_access_key) are encrypted
    at rest using AES-256-GCM before being written to this table.
    """
    __tablename__ = 'aws_credentials'

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Encrypted storage – plain values MUST NOT be stored directly
    aws_access_key_id = Column(Text, nullable=False)          # AES-GCM encrypted
    aws_secret_access_key = Column(Text, nullable=False)      # AES-GCM encrypted
    default_region = Column(String(64), nullable=False)
    default_output_format = Column(String(16), nullable=False, default='json')
    bucket_name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    def to_safe_dict(self):
        """Return a dict safe for JSON serialisation (no secret values)."""
        return {
            "id": self.id,
            "aws_access_key_id": "****" + (self._masked_key() or ""),
            "default_region": self.default_region,
            "default_output_format": self.default_output_format,
            "bucket_name": self.bucket_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def _masked_key(self):
        """Return the last 4 chars of the decrypted access key id for display."""
        try:
            from cps.aws.awsS3 import decrypt_value
            plain = decrypt_value(self.aws_access_key_id)
            return plain[-4:] if len(plain) >= 4 else plain
        except Exception:
            return ""

    def __repr__(self):
        return f'<AWSCredentials id={self.id} bucket={self.bucket_name}>'

