# -*- coding: utf-8 -*-
"""
Reusable AWS S3 storage service.

All application code talks to S3 through S3StorageService; obtain one with
get_storage(), which returns None when S3 storage is disabled or not
configured, so callers can fall back to local storage.
"""

import os
import re
import uuid
import threading
import datetime
from typing import Optional, Dict, Any, Iterable

import boto3
from boto3.exceptions import S3UploadFailedError
from botocore.config import Config
from botocore.exceptions import (
    ClientError, NoCredentialsError, PartialCredentialsError, EndpointConnectionError,
    ConnectTimeoutError, ReadTimeoutError, ConnectionClosedError, BotoCoreError,
)

from .. import logger
from .s3Config import S3Settings, load_s3_settings

log = logger.create()

KEY_CATEGORIES = ("books", "images", "videos", "documents", "uploads")

_INVALID_CREDENTIAL_CODES = {"InvalidAccessKeyId", "SignatureDoesNotMatch", "InvalidClientTokenId",
                             "ExpiredToken", "TokenRefreshRequired", "AuthorizationHeaderMalformed"}
_ACCESS_DENIED_CODES = {"AccessDenied", "403", "Forbidden", "AllAccessDisabled", "AccountProblem"}
_NOT_FOUND_CODES = {"NoSuchKey", "404", "NotFound"}


class StorageError(Exception):
    """An S3 operation failed. `message` is safe to show to users (no credentials)."""

    def __init__(self, message: str, code: str = "storage_error", status: int = 502):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def translate_error(exc: Exception, action: str, bucket: str, key: Optional[str] = None) -> StorageError:
    target = "'{}'".format(key) if key else "bucket '{}'".format(bucket)
    if isinstance(exc, StorageError):
        return exc
    if isinstance(exc, (NoCredentialsError, PartialCredentialsError)):
        return StorageError("AWS credentials are missing or incomplete", "invalid_credentials", 503)
    if isinstance(exc, (EndpointConnectionError, ConnectTimeoutError, ReadTimeoutError, ConnectionClosedError)):
        return StorageError("Could not reach AWS S3 (network error) while trying to {} {}".format(action, target),
                            "network_error", 503)

    code = ""
    if isinstance(exc, ClientError):
        code = str(exc.response.get("Error", {}).get("Code", ""))
    elif isinstance(exc, S3UploadFailedError):
        # upload_file/upload_fileobj wrap the ClientError into a message string
        match = re.search(r"\(([A-Za-z0-9]+)\)", str(exc))
        code = match.group(1) if match else ""

    if code == "NoSuchBucket":
        return StorageError("S3 bucket '{}' does not exist".format(bucket), "missing_bucket", 503)
    if code in _INVALID_CREDENTIAL_CODES:
        return StorageError("AWS rejected the configured credentials ({})".format(code), "invalid_credentials", 503)
    if code in _ACCESS_DENIED_CODES:
        return StorageError("Access denied by AWS while trying to {} {}".format(action, target), "access_denied", 503)
    if code in _NOT_FOUND_CODES:
        return StorageError("Object {} was not found in S3".format(target), "not_found", 404)
    if code:
        return StorageError("AWS S3 error ({}) while trying to {} {}".format(code, action, target), "aws_error", 502)
    if isinstance(exc, BotoCoreError):
        return StorageError("AWS S3 client error while trying to {} {}".format(action, target), "aws_error", 502)
    return StorageError("Unexpected storage error while trying to {} {}".format(action, target), "storage_error", 500)


_SEGMENT_RE = re.compile(r"[^a-z0-9_-]+")


def _clean_segment(value) -> str:
    segment = _SEGMENT_RE.sub("-", str(value).lower()).strip("-")
    if not segment:
        raise ValueError("Invalid object key segment: {!r}".format(value))
    return segment[:64]


class S3StorageService:
    def __init__(self, settings: S3Settings, client=None):
        self.settings = settings
        self._client = client
        self._lock = threading.Lock()

    @property
    def bucket(self) -> str:
        return self.settings.bucket

    # ------------------------------------------------------------------ client
    def _new_client(self, region: str):
        kwargs: Dict[str, Any] = {
            "region_name": region,
            "config": Config(signature_version="s3v4",
                             retries={"max_attempts": 5, "mode": "standard"},
                             connect_timeout=10, read_timeout=60),
        }
        if self.settings.endpoint_url:
            kwargs["endpoint_url"] = self.settings.endpoint_url
        if self.settings.access_key and self.settings.secret_key:
            kwargs["aws_access_key_id"] = self.settings.access_key
            kwargs["aws_secret_access_key"] = self.settings.secret_key
        return boto3.client("s3", **kwargs)

    @property
    def client(self):
        if self._client is None:
            with self._lock:
                if self._client is None:
                    client = self._new_client(self.settings.region)
                    region = self._bucket_region(client)
                    if region and region != self.settings.region and not self.settings.endpoint_url:
                        log.info("S3 bucket '%s' is in region %s (configured: %s)",
                                 self.bucket, region, self.settings.region)
                        client = self._new_client(region)
                    self._client = client
        return self._client

    def _bucket_region(self, client) -> Optional[str]:
        """Real bucket region, so presigned URLs are signed for the right endpoint.
        Needs s3:GetBucketLocation; without it the configured region is used."""
        try:
            loc = client.get_bucket_location(Bucket=self.bucket).get("LocationConstraint")
            return "us-east-1" if loc in (None, "") else ("eu-west-1" if loc == "EU" else loc)
        except Exception as e:
            log.debug("Could not determine region of bucket '%s': %s", self.bucket, e)
            return None

    # -------------------------------------------------------------------- keys
    def build_key(self, category: str, scope: Iterable = (), extension: str = "") -> str:
        """
        Build a unique object key: [prefix]<category>/<scope...>/<uuid>.<ext>
        e.g. books/42/3f2c...e1.epub, images/uploads/u7/2026/11/9ab0...c2.png
        No client-supplied filename is ever used, which rules out path traversal.
        """
        if category not in KEY_CATEGORIES:
            raise ValueError("Unknown storage category: {}".format(category))
        extension = (extension or "").lower().lstrip(".")
        if extension and not re.fullmatch(r"[a-z0-9]{1,10}", extension):
            raise ValueError("Invalid file extension: {!r}".format(extension))
        parts = [category] + [_clean_segment(s) for s in scope]
        name = uuid.uuid4().hex + ("." + extension if extension else "")
        return self.settings.prefix + "/".join(parts + [name])

    @staticmethod
    def dated_scope(*scope) -> list:
        now = datetime.datetime.utcnow()
        return list(scope) + [now.strftime("%Y"), now.strftime("%m")]

    # -------------------------------------------------------------- operations
    def _extra_args(self, content_type: str, original_filename: Optional[str]) -> Dict[str, Any]:
        extra = {"ContentType": content_type or "application/octet-stream", "ServerSideEncryption": "AES256"}
        if original_filename:
            # S3 user metadata must be ASCII
            extra["Metadata"] = {"original-filename": original_filename.encode("ascii", "ignore").decode()[:255]}
        return extra

    def upload_fileobj(self, fileobj, key: str, content_type: str,
                       original_filename: Optional[str] = None) -> Dict[str, Any]:
        try:
            fileobj.seek(0)
            self.client.upload_fileobj(fileobj, self.bucket, key,
                                       ExtraArgs=self._extra_args(content_type, original_filename))
            head = self.client.head_object(Bucket=self.bucket, Key=key)
        except Exception as e:
            err = translate_error(e, "upload", self.bucket, key)
            log.error("S3 upload failed for key %s: %s", key, err.message)
            raise err
        log.info("Uploaded %s to s3://%s/%s (%s bytes)", original_filename or "file", self.bucket, key,
                 head.get("ContentLength"))
        return {"key": key, "size": head.get("ContentLength", 0), "etag": head.get("ETag", "").strip('"')}

    def upload_path(self, path: str, key: str, content_type: str,
                    original_filename: Optional[str] = None) -> Dict[str, Any]:
        with open(path, "rb") as f:
            return self.upload_fileobj(f, key, content_type, original_filename)

    def download_to_path(self, key: str, dest_path: str) -> None:
        """Download an object atomically: written to a temp file first, then moved into place."""
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        tmp_path = "{}.s3part-{}".format(dest_path, uuid.uuid4().hex[:8])
        try:
            self.client.download_file(self.bucket, key, tmp_path)
            os.replace(tmp_path, dest_path)
        except Exception as e:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            if isinstance(e, OSError) and not isinstance(e, BotoCoreError):
                log.error("Could not write %s restored from S3: %s", dest_path, e)
                raise StorageError("Could not write restored file to local storage", "local_io_error", 500)
            err = translate_error(e, "download", self.bucket, key)
            log.error("S3 download failed for key %s: %s", key, err.message)
            raise err

    def delete_object(self, key: str) -> None:
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except Exception as e:
            err = translate_error(e, "delete", self.bucket, key)
            if err.code == "not_found":
                return
            log.error("S3 delete failed for key %s: %s", key, err.message)
            raise err
        log.info("Deleted s3://%s/%s", self.bucket, key)

    def object_exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception as e:
            err = translate_error(e, "read", self.bucket, key)
            if err.code == "not_found":
                return False
            raise err

    def presigned_url(self, key: str, download_name: Optional[str] = None,
                      content_type: Optional[str] = None, content_disposition: Optional[str] = None,
                      inline: bool = False, expires: Optional[int] = None) -> str:
        params: Dict[str, Any] = {"Bucket": self.bucket, "Key": key}
        if content_disposition:
            params["ResponseContentDisposition"] = content_disposition
        elif download_name:
            from urllib.parse import quote
            safe = download_name.encode("ascii", "ignore").decode().replace('"', "") or "file"
            params["ResponseContentDisposition"] = '{}; filename="{}"; filename*=UTF-8\'\'{}'.format(
                "inline" if inline else "attachment", safe, quote(download_name))
        if content_type:
            params["ResponseContentType"] = content_type
        try:
            return self.client.generate_presigned_url("get_object", Params=params,
                                                      ExpiresIn=expires or self.settings.presign_expiry)
        except Exception as e:
            err = translate_error(e, "sign a URL for", self.bucket, key)
            log.error("Presigning failed for key %s: %s", key, err.message)
            raise err

    def check_connection(self) -> Dict[str, Any]:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception as e:
            err = translate_error(e, "access", self.bucket)
            if err.code == "not_found":
                err = StorageError("S3 bucket '{}' does not exist".format(self.bucket), "missing_bucket", 503)
            return {"success": False, "message": err.message, "code": err.code}
        return {"success": True, "message": "Bucket '{}' is reachable".format(self.bucket)}


_service_cache: Dict[str, S3StorageService] = {}
_cache_lock = threading.Lock()


def get_storage(session=None, for_cleanup=False) -> Optional[S3StorageService]:
    """
    Return the S3 storage service for the current configuration, or None if S3 is not in use.
    for_cleanup=True returns the service even while the admin switch is off (for deletions).
    """
    settings = load_s3_settings(session, for_cleanup=for_cleanup)
    if settings is None:
        return None
    key = settings.fingerprint + settings.prefix + str(settings.presign_expiry) + str(settings.serve_downloads)
    with _cache_lock:
        service = _service_cache.get(key)
        if service is None:
            _service_cache.clear()   # configuration changed - drop stale clients
            service = S3StorageService(settings)
            _service_cache[key] = service
            log.info("S3 storage active: bucket '%s' (%s credentials)", settings.bucket, settings.source)
        return service
