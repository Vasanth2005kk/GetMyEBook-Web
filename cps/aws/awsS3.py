# -*- coding: utf-8 -*-
"""
AWS S3 Service Layer
Handles all AWS S3 operations with encrypted credential management.
"""

import os
import base64
import json
import logging
from io import BytesIO
from typing import Optional, Dict, Any, List

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid AWS regions – extend as needed
# ---------------------------------------------------------------------------
VALID_AWS_REGIONS = [
    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
    "af-south-1",
    "ap-east-1", "ap-south-1", "ap-south-2",
    "ap-southeast-1", "ap-southeast-2", "ap-southeast-3", "ap-southeast-4",
    "ap-northeast-1", "ap-northeast-2", "ap-northeast-3",
    "ca-central-1", "ca-west-1",
    "eu-central-1", "eu-central-2",
    "eu-west-1", "eu-west-2", "eu-west-3",
    "eu-north-1", "eu-south-1", "eu-south-2",
    "il-central-1",
    "me-central-1", "me-south-1",
    "sa-east-1",
]

VALID_OUTPUT_FORMATS = ["json", "yaml", "text", "table"]

# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------

def _get_encryption_key() -> bytes:
    """Derive a 32-byte AES key from the app SECRET_KEY."""
    secret = os.environ.get("SECRET_KEY", "default-fallback-secret-key-change-me")
    salt = b"getmyebook_aws_s3_salt_v1"
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    return kdf.derive(secret.encode())


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string value using AES-256-GCM.
    Returns a base64-encoded string: nonce(12) + ciphertext."""
    if not plaintext:
        return ""
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt_value(token: str) -> str:
    """Decrypt a value produced by encrypt_value."""
    if not token:
        return ""
    try:
        data = base64.b64decode(token.encode())
        nonce, ct = data[:12], data[12:]
        key = _get_encryption_key()
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ct, None).decode()
    except Exception as e:
        log.error(f"Decryption failed: {e}")
        return ""


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_credentials_payload(data: Dict[str, Any]) -> Optional[str]:
    """
    Validates incoming AWS credential fields.
    Returns None on success, or an error message string on failure.
    """
    required = [
        "aws_access_key_id",
        "aws_secret_access_key",
        "default_region",
        "bucket_name",
    ]
    for field in required:
        if not data.get(field, "").strip():
            return f"Field '{field}' is required and cannot be empty."

    region = data.get("default_region", "").strip()
    if region not in VALID_AWS_REGIONS:
        return (
            f"Invalid AWS region '{region}'. "
            f"Must be one of: {', '.join(VALID_AWS_REGIONS)}"
        )

    output_fmt = data.get("default_output_format", "json").strip()
    if output_fmt and output_fmt not in VALID_OUTPUT_FORMATS:
        return (
            f"Invalid output format '{output_fmt}'. "
            f"Must be one of: {', '.join(VALID_OUTPUT_FORMATS)}"
        )

    return None


# ---------------------------------------------------------------------------
# S3 client factory
# ---------------------------------------------------------------------------

def _build_s3_client(access_key: str, secret_key: str, region: str):
    """Build and return a boto3 S3 client."""
    import boto3
    return boto3.client(
        "s3",
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )


# ---------------------------------------------------------------------------
# Core S3 operations  (all accept raw/plain-text credentials)
# ---------------------------------------------------------------------------

def test_s3_connection(access_key: str, secret_key: str, region: str, bucket_name: str) -> Dict[str, Any]:
    """
    Test S3 connectivity and bucket access.
    Returns {"success": bool, "message": str, "details": dict}
    """
    try:
        client = _build_s3_client(access_key, secret_key, region)

        # 1) Verify credentials are accepted at all
        sts_client = __import__("boto3").client(
            "sts",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        identity = sts_client.get_caller_identity()

        # 2) Check bucket exists and is accessible
        client.head_bucket(Bucket=bucket_name)

        return {
            "success": True,
            "message": f"Connected successfully! Bucket '{bucket_name}' is accessible.",
            "details": {
                "account_id": identity.get("Account"),
                "arn": identity.get("Arn"),
                "bucket": bucket_name,
                "region": region,
            },
        }

    except __import__("botocore").exceptions.ClientError as e:
        code = e.response["Error"]["Code"]
        msg = e.response["Error"]["Message"]
        if code in ("403", "AccessDenied"):
            return {"success": False, "message": f"Access Denied: {msg}", "details": {}}
        if code in ("404", "NoSuchBucket"):
            return {"success": False, "message": f"Bucket '{bucket_name}' does not exist.", "details": {}}
        if code == "InvalidClientTokenId":
            return {"success": False, "message": "Invalid AWS Access Key ID.", "details": {}}
        if code == "SignatureDoesNotMatch":
            return {"success": False, "message": "Invalid AWS Secret Access Key.", "details": {}}
        return {"success": False, "message": f"AWS Error ({code}): {msg}", "details": {}}
    except Exception as e:
        return {"success": False, "message": str(e), "details": {}}


def upload_file_to_s3(
    access_key: str,
    secret_key: str,
    region: str,
    bucket_name: str,
    file_obj,
    s3_key: str,
    content_type: str = "application/octet-stream",
) -> Dict[str, Any]:
    """Upload a file-like object to S3."""
    try:
        client = _build_s3_client(access_key, secret_key, region)
        client.upload_fileobj(
            file_obj,
            bucket_name,
            s3_key,
            ExtraArgs={"ContentType": content_type},
        )
        url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{s3_key}"
        return {"success": True, "message": "File uploaded successfully.", "url": url, "key": s3_key}
    except Exception as e:
        log.error(f"S3 upload error: {e}")
        return {"success": False, "message": str(e)}


def list_bucket_files(
    access_key: str,
    secret_key: str,
    region: str,
    bucket_name: str,
    prefix: str = "",
    max_keys: int = 100,
) -> Dict[str, Any]:
    """List files in an S3 bucket with optional prefix."""
    try:
        client = _build_s3_client(access_key, secret_key, region)
        kwargs: Dict[str, Any] = {"Bucket": bucket_name, "MaxKeys": max_keys}
        if prefix:
            kwargs["Prefix"] = prefix

        response = client.list_objects_v2(**kwargs)
        files: List[Dict[str, Any]] = []
        for obj in response.get("Contents", []):
            files.append({
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat(),
                "etag": obj.get("ETag", "").strip('"'),
                "url": f"https://{bucket_name}.s3.{region}.amazonaws.com/{obj['Key']}",
            })
        return {
            "success": True,
            "files": files,
            "count": len(files),
            "truncated": response.get("IsTruncated", False),
        }
    except Exception as e:
        log.error(f"S3 list error: {e}")
        return {"success": False, "message": str(e), "files": []}


def delete_bucket_file(
    access_key: str,
    secret_key: str,
    region: str,
    bucket_name: str,
    s3_key: str,
) -> Dict[str, Any]:
    """Delete a single file from S3."""
    try:
        client = _build_s3_client(access_key, secret_key, region)
        client.delete_object(Bucket=bucket_name, Key=s3_key)
        return {"success": True, "message": f"File '{s3_key}' deleted successfully."}
    except Exception as e:
        log.error(f"S3 delete error: {e}")
        return {"success": False, "message": str(e)}
