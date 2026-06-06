# -*- coding: utf-8 -*-
"""
Admin Blueprint – AWS S3 Credential Management & S3 File Operations
Routes are mounted at /admin/aws-s3/...
All routes require admin login.
"""

import json
import datetime
from functools import wraps

from flask import Blueprint, request, jsonify, render_template, flash, redirect, url_for, abort
from ..cw_login import current_user

from .. import ub, logger
from .awsS3 import (
    encrypt_value,
    decrypt_value,
    validate_credentials_payload,
    test_s3_connection,
    upload_file_to_s3,
    list_bucket_files,
    delete_bucket_file,
    VALID_AWS_REGIONS,
    VALID_OUTPUT_FORMATS,
)

log = logger.create()

# Serve templates and static files from the package folder
# Use an explicit static_url_path to avoid colliding with the app's global /static
aws_s3 = Blueprint(
    "aws_s3",
    __name__,
    template_folder="templates",
    static_folder="static",
    static_url_path="/aws_s3/static",
)

# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

def admin_required(f):
    """Ensure the caller is an authenticated admin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.role_admin():
            abort(403)
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Helper – load single credential record (there is ever only ONE row)
# ---------------------------------------------------------------------------

def _get_creds_record():
    """Return the first AWSCredentials row, or None."""
    try:
        return ub.session.query(ub.AWSCredentials).first()
    except Exception as e:
        log.error(f"DB query error (aws_credentials): {e}")
        return None


def _get_plain_creds(record: ub.AWSCredentials):
    """Return a dict with decrypted plain-text credentials from a DB record."""
    return {
        "access_key": decrypt_value(record.aws_access_key_id),
        "secret_key": decrypt_value(record.aws_secret_access_key),
        "region": record.default_region,
        "bucket": record.bucket_name,
    }


# ---------------------------------------------------------------------------
# UI page
# ---------------------------------------------------------------------------

@aws_s3.route("/admin/aws-s3", methods=["GET"])
@admin_required
def aws_s3_page():
    """Render the AWS S3 admin configuration page."""
    record = _get_creds_record()
    credential = None
    if record:
        credential = {
            "id": record.id,
            "aws_access_key_id_masked": "****" + (record._masked_key() or ""),
            "default_region": record.default_region,
            "default_output_format": record.default_output_format,
            "bucket_name": record.bucket_name,
            "created_at": record.created_at.strftime("%Y-%m-%d %H:%M UTC") if record.created_at else "",
            "updated_at": record.updated_at.strftime("%Y-%m-%d %H:%M UTC") if record.updated_at else "",
        }
    return render_template(
        "awsAdminPanel.html",
        credential=credential,
        regions=VALID_AWS_REGIONS,
        output_formats=VALID_OUTPUT_FORMATS,
        title="AWS S3 Configuration",
        page="aws-s3",
    )


# ---------------------------------------------------------------------------
# API – Add credentials
# ---------------------------------------------------------------------------

@aws_s3.route("/admin/aws-s3/credentials", methods=["POST"])
@admin_required
def add_credentials():
    """
    POST /admin/aws-s3/credentials
    Body (JSON): aws_access_key_id, aws_secret_access_key,
                 default_region, default_output_format, bucket_name
    """
    data = request.get_json(silent=True) or {}

    error = validate_credentials_payload(data)
    if error:
        return jsonify({"success": False, "message": error}), 400

    existing = _get_creds_record()
    if existing:
        return jsonify({
            "success": False,
            "message": "Credentials already exist. Use the update endpoint.",
        }), 409

    try:
        record = ub.AWSCredentials(
            aws_access_key_id=encrypt_value(data["aws_access_key_id"].strip()),
            aws_secret_access_key=encrypt_value(data["aws_secret_access_key"].strip()),
            default_region=data["default_region"].strip(),
            default_output_format=data.get("default_output_format", "json").strip() or "json",
            bucket_name=data["bucket_name"].strip(),
        )
        ub.session.add(record)
        ub.session.commit()
        log.info(f"AWS credentials added (id={record.id}) by user '{current_user.name}'")
        return jsonify({"success": True, "message": "AWS credentials saved successfully.", "id": record.id}), 201
    except Exception as e:
        ub.session.rollback()
        log.error(f"Failed to save AWS credentials: {e}")
        return jsonify({"success": False, "message": "Database error while saving credentials."}), 500


# ---------------------------------------------------------------------------
# API – Update credentials
# ---------------------------------------------------------------------------

@aws_s3.route("/admin/aws-s3/credentials/<int:cred_id>", methods=["PUT"])
@admin_required
def update_credentials(cred_id):
    """
    PUT /admin/aws-s3/credentials/<id>
    Partial update is supported – only supplied fields are updated.
    """
    data = request.get_json(silent=True) or {}

    record = ub.session.query(ub.AWSCredentials).filter(ub.AWSCredentials.id == cred_id).first()
    if not record:
        return jsonify({"success": False, "message": "Credentials record not found."}), 404

    # Build a merged dict to run full validation
    merged = {
        "aws_access_key_id": decrypt_value(record.aws_access_key_id),
        "aws_secret_access_key": decrypt_value(record.aws_secret_access_key),
        "default_region": record.default_region,
        "default_output_format": record.default_output_format,
        "bucket_name": record.bucket_name,
    }
    for k in merged:
        if k in data and data[k].strip():
            merged[k] = data[k].strip()

    error = validate_credentials_payload(merged)
    if error:
        return jsonify({"success": False, "message": error}), 400

    try:
        if "aws_access_key_id" in data and data["aws_access_key_id"].strip():
            record.aws_access_key_id = encrypt_value(data["aws_access_key_id"].strip())
        if "aws_secret_access_key" in data and data["aws_secret_access_key"].strip():
            record.aws_secret_access_key = encrypt_value(data["aws_secret_access_key"].strip())
        if "default_region" in data and data["default_region"].strip():
            record.default_region = data["default_region"].strip()
        if "default_output_format" in data:
            record.default_output_format = data["default_output_format"].strip() or "json"
        if "bucket_name" in data and data["bucket_name"].strip():
            record.bucket_name = data["bucket_name"].strip()

        record.updated_at = datetime.datetime.utcnow()
        ub.session.commit()
        log.info(f"AWS credentials updated (id={cred_id}) by user '{current_user.name}'")
        return jsonify({"success": True, "message": "AWS credentials updated successfully."})
    except Exception as e:
        ub.session.rollback()
        log.error(f"Failed to update AWS credentials: {e}")
        return jsonify({"success": False, "message": "Database error while updating credentials."}), 500


# ---------------------------------------------------------------------------
# API – Delete credentials
# ---------------------------------------------------------------------------

@aws_s3.route("/admin/aws-s3/credentials/<int:cred_id>", methods=["DELETE"])
@admin_required
def delete_credentials(cred_id):
    """DELETE /admin/aws-s3/credentials/<id>"""
    record = ub.session.query(ub.AWSCredentials).filter(ub.AWSCredentials.id == cred_id).first()
    if not record:
        return jsonify({"success": False, "message": "Credentials record not found."}), 404
    try:
        ub.session.delete(record)
        ub.session.commit()
        log.info(f"AWS credentials deleted (id={cred_id}) by user '{current_user.name}'")
        return jsonify({"success": True, "message": "AWS credentials deleted successfully."})
    except Exception as e:
        ub.session.rollback()
        log.error(f"Failed to delete AWS credentials: {e}")
        return jsonify({"success": False, "message": "Database error while deleting credentials."}), 500


# ---------------------------------------------------------------------------
# API – Test connection
# ---------------------------------------------------------------------------

@aws_s3.route("/admin/aws-s3/test-connection", methods=["POST"])
@admin_required
def test_connection():
    """
    POST /admin/aws-s3/test-connection
    Body can contain credentials directly (for first-save test) OR be empty
    (uses stored credentials).
    """
    data = request.get_json(silent=True) or {}

    # Prefer credentials from request body; fallback to stored record
    access_key = data.get("aws_access_key_id", "").strip()
    secret_key = data.get("aws_secret_access_key", "").strip()
    region = data.get("default_region", "").strip()
    bucket_name = data.get("bucket_name", "").strip()

    if not (access_key and secret_key and region and bucket_name):
        record = _get_creds_record()
        if not record:
            return jsonify({"success": False, "message": "No credentials found. Please save credentials first."}), 400
        creds = _get_plain_creds(record)
        access_key = access_key or creds["access_key"]
        secret_key = secret_key or creds["secret_key"]
        region = region or creds["region"]
        bucket_name = bucket_name or creds["bucket"]

    if not (access_key and secret_key and region and bucket_name):
        return jsonify({"success": False, "message": "Incomplete credentials for connection test."}), 400

    result = test_s3_connection(access_key, secret_key, region, bucket_name)
    status = 200 if result["success"] else 400
    return jsonify(result), status


# ---------------------------------------------------------------------------
# API – Upload file
# ---------------------------------------------------------------------------

@aws_s3.route("/admin/aws-s3/upload", methods=["POST"])
@admin_required
def upload_file():
    """
    POST /admin/aws-s3/upload  (multipart/form-data)
    Form fields: file (required), s3_key (optional – defaults to original filename)
    """
    record = _get_creds_record()
    if not record:
        return jsonify({"success": False, "message": "AWS credentials not configured."}), 400

    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file part in the request."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "message": "No file selected."}), 400

    s3_key = request.form.get("s3_key", "").strip() or file.filename
    content_type = file.content_type or "application/octet-stream"

    creds = _get_plain_creds(record)
    result = upload_file_to_s3(
        creds["access_key"], creds["secret_key"],
        creds["region"], creds["bucket"],
        file.stream, s3_key, content_type,
    )
    status = 200 if result["success"] else 500
    return jsonify(result), status


# ---------------------------------------------------------------------------
# API – List bucket files
# ---------------------------------------------------------------------------

@aws_s3.route("/admin/aws-s3/files", methods=["GET"])
@admin_required
def list_files():
    """
    GET /admin/aws-s3/files?prefix=<optional>&max_keys=<optional>
    """
    record = _get_creds_record()
    if not record:
        return jsonify({"success": False, "message": "AWS credentials not configured.", "files": []}), 400

    prefix = request.args.get("prefix", "")
    try:
        max_keys = int(request.args.get("max_keys", 100))
        max_keys = min(max(1, max_keys), 1000)
    except ValueError:
        max_keys = 100

    creds = _get_plain_creds(record)
    result = list_bucket_files(
        creds["access_key"], creds["secret_key"],
        creds["region"], creds["bucket"],
        prefix, max_keys,
    )
    status = 200 if result["success"] else 500
    return jsonify(result), status


# ---------------------------------------------------------------------------
# API – Delete bucket file
# ---------------------------------------------------------------------------

@aws_s3.route("/admin/aws-s3/files", methods=["DELETE"])
@admin_required
def delete_file():
    """
    DELETE /admin/aws-s3/files
    Body (JSON): { "key": "path/to/file.pdf" }
    """
    record = _get_creds_record()
    if not record:
        return jsonify({"success": False, "message": "AWS credentials not configured."}), 400

    data = request.get_json(silent=True) or {}
    s3_key = data.get("key", "").strip()
    if not s3_key:
        return jsonify({"success": False, "message": "No file key provided."}), 400

    creds = _get_plain_creds(record)
    result = delete_bucket_file(
        creds["access_key"], creds["secret_key"],
        creds["region"], creds["bucket"],
        s3_key,
    )
    status = 200 if result["success"] else 500
    return jsonify(result), status
