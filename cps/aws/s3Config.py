# -*- coding: utf-8 -*-
"""
AWS S3 storage configuration.

Resolution order:
  1. Credentials saved in the admin panel (/admin/aws-s3, table aws_credentials)
  2. Environment variables: AWS_S3_BUCKET + AWS_S3_REGION, credentials taken
     from the standard boto3 chain (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY,
     ~/.aws profile, or an attached IAM role - preferred in production)

S3 storage is used only while the admin panel switch is on (settings.aws_active)
and it is not switched off by AWS_S3_ENABLED=false (the older AWSConfig variable
is honoured when AWS_S3_ENABLED is not set). Otherwise files are stored in the
local library folder only.
"""

import os
import re
import hashlib
from dataclasses import dataclass, field
from typing import Optional

from .. import logger, ub, config
from ..models.awstbl import AWSCredentials
from .awsS3 import decrypt_value

log = logger.create()

DEFAULT_PRESIGN_EXPIRY = 900          # 15 minutes
MAX_PRESIGN_EXPIRY = 7 * 24 * 3600    # S3 SigV4 hard limit


def env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def env_int(name: str, default: int, minimum: int = 0, maximum: Optional[int] = None) -> int:
    try:
        value = int(os.environ.get(name, default))
    except (TypeError, ValueError):
        log.warning("Invalid integer for %s, using default %s", name, default)
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def s3_env_enabled() -> bool:
    """Deployment-level switch (environment)."""
    if os.environ.get("AWS_S3_ENABLED", "").strip():
        return env_bool("AWS_S3_ENABLED", True)
    return env_bool("AWSConfig", True)


def s3_admin_enabled() -> bool:
    """Admin panel switch; on unless an admin turned it off."""
    return getattr(config, "aws_active", True) is not False


def s3_enabled() -> bool:
    """True when new files should go to S3."""
    return s3_env_enabled() and s3_admin_enabled()


def _clean_prefix(prefix: str) -> str:
    """Normalise an optional root prefix, e.g. ' /prod//getmyebook ' -> 'prod/getmyebook/'."""
    parts = [re.sub(r"[^a-zA-Z0-9._-]", "-", p) for p in (prefix or "").split("/")]
    parts = [p for p in parts if p and p not in (".", "..")]
    return "/".join(parts) + "/" if parts else ""


@dataclass(frozen=True)
class S3Settings:
    bucket: str
    region: str
    source: str                                         # "admin" | "environment"
    access_key: Optional[str] = field(default=None, repr=False)
    secret_key: Optional[str] = field(default=None, repr=False)
    endpoint_url: Optional[str] = None
    prefix: str = ""
    presign_expiry: int = DEFAULT_PRESIGN_EXPIRY
    serve_downloads: bool = True

    @property
    def fingerprint(self) -> str:
        """Stable cache key for clients built from these settings (no secrets in clear text)."""
        raw = "|".join([self.bucket, self.region, self.endpoint_url or "",
                        self.access_key or "", self.secret_key or ""])
        return hashlib.sha256(raw.encode()).hexdigest()


def _settings_from_admin_record(session) -> Optional[S3Settings]:
    if session is None:
        return None
    try:
        record = session.query(AWSCredentials).first()
    except Exception as e:
        log.warning("Could not read AWS credentials from database: %s", e)
        try:
            session.rollback()
        except Exception:
            pass
        return None
    if not record or not record.bucket_name:
        return None
    secret = decrypt_value(record.aws_secret_access_key)
    if not secret:
        log.error("Stored AWS secret key could not be decrypted (was SECRET_KEY changed?); "
                  "re-enter the credentials in the AWS S3 admin panel")
        return None
    return S3Settings(
        bucket=record.bucket_name.strip(),
        region=(record.default_region or "us-east-1").strip(),
        source="admin",
        access_key=(record.aws_access_key_id or "").strip(),
        secret_key=secret,
    )


def _settings_from_environment() -> Optional[S3Settings]:
    bucket = os.environ.get("AWS_S3_BUCKET", "").strip()
    if not bucket:
        return None
    region = (os.environ.get("AWS_S3_REGION") or os.environ.get("AWS_REGION")
              or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1").strip()
    # access_key/secret_key stay None: boto3 resolves them from its default chain
    return S3Settings(bucket=bucket, region=region, source="environment")


def load_s3_settings(session=None, for_cleanup=False) -> Optional[S3Settings]:
    """
    Return the active S3Settings, or None when S3 storage is disabled / not configured.
    for_cleanup=True ignores the admin panel switch: objects stored while the switch
    was on must still be deletable after it was turned off.
    """
    if not (s3_env_enabled() if for_cleanup else s3_enabled()):
        return None
    base = _settings_from_admin_record(session if session is not None else ub.session)
    if base is None:
        base = _settings_from_environment()
    if base is None:
        return None
    return S3Settings(
        bucket=base.bucket,
        region=base.region,
        source=base.source,
        access_key=base.access_key,
        secret_key=base.secret_key,
        endpoint_url=os.environ.get("AWS_S3_ENDPOINT_URL", "").strip() or None,
        prefix=_clean_prefix(os.environ.get("AWS_S3_PREFIX", "")),
        presign_expiry=env_int("AWS_S3_PRESIGNED_EXPIRY", DEFAULT_PRESIGN_EXPIRY, 60, MAX_PRESIGN_EXPIRY),
        serve_downloads=env_bool("AWS_S3_SERVE_DOWNLOADS", True),
    )
