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
from ..models.awstbl import AWSCredentials

from .. import ub, logger
from .awsS3 import (
    encrypt_value,
    decrypt_value,
    validate_credentials_payload,
    test_s3_connection,
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
        return ub.session.query(AWSCredentials).first()
    except Exception as e:
        log.error(f"DB query error (aws_credentials): {e}")
        return None


def _get_plain_creds(record: AWSCredentials):
    """Return a dict with credentials from a DB record.
    NOTE: aws_access_key_id is stored as plain text;
          aws_secret_access_key is AES-GCM encrypted.
    """
    return {
        "access_key": record.aws_access_key_id,
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
            "aws_access_key_id": "*****" + (record.aws_access_key_id[-4:] if record.aws_access_key_id else ""),
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
    # Accept JSON (AJAX) or HTML form submissions
    data = request.get_json(silent=True) or {}
    if not data and request.form:
        # form data fallback
        data = request.form.to_dict()

    error = validate_credentials_payload(data)
    if error:
        is_ajax = request.is_json or request.headers.get('X-CSRFToken')
        if is_ajax:
            return jsonify({"success": False, "message": error}), 400
        flash(error, "error")
        return redirect(url_for('aws_s3.aws_s3_page'))

    existing = _get_creds_record()
    if existing and not request.form.get("_method") == "PUT":
        # If credentials exist and this is not a form-based update, reject
        if request.is_json:
            return jsonify({"success": False, "message": "Credentials already exist. Use the update endpoint."}), 409
        flash("Credentials already exist. Use the update flow to modify.", "error")
        return redirect(url_for('aws_s3.aws_s3_page'))

    try:
        record = AWSCredentials(
            aws_access_key_id=data["aws_access_key_id"].strip(),
            aws_secret_access_key=encrypt_value(data["aws_secret_access_key"].strip()),
            default_region=data["default_region"].strip(),
            default_output_format=data.get("default_output_format", "json").strip() or "json",
            bucket_name=data["bucket_name"].strip(),
        )
        ub.session.add(record)
        ub.session.commit()
        log.info(f"AWS credentials added (id={record.id}) by user '{current_user.name}'")
        if request.is_json:
            return jsonify({"success": True, "message": "AWS credentials saved successfully.", "id": record.id}), 201
        flash("AWS credentials saved successfully.", "success")
        return redirect(url_for('aws_s3.aws_s3_page'))
    except Exception as e:
        ub.session.rollback()
        log.error(f"Failed to save AWS credentials: {e}")
        if request.is_json:
            return jsonify({"success": False, "message": "Database error while saving credentials."}), 500
        flash("Database error while saving credentials.", "error")
        return redirect(url_for('aws_s3.aws_s3_page'))


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

    record = ub.session.query(AWSCredentials).filter(AWSCredentials.id == cred_id).first()
    if not record:
        return jsonify({"success": False, "message": "Credentials record not found."}), 404

    # Build a merged dict to run full validation
    merged = {
        "aws_access_key_id": record.aws_access_key_id,
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
        # aws_access_key_id is stored as plain text (not encrypted)
        if "aws_access_key_id" in data and data["aws_access_key_id"].strip():
            record.aws_access_key_id = data["aws_access_key_id"].strip()
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
    is_ajax = request.is_json or request.headers.get('X-CSRFToken') or request.method == 'DELETE'
    record = ub.session.query(AWSCredentials).filter(AWSCredentials.id == cred_id).first()
    if not record:
        if is_ajax:
            return jsonify({"success": False, "message": "Credentials record not found."}), 404
        flash("Credentials record not found.", "error")
        return redirect(url_for('aws_s3.aws_s3_page'))
    try:
        ub.session.delete(record)
        ub.session.commit()
        log.info(f"AWS credentials deleted (id={cred_id}) by user '{current_user.name}'")
        if is_ajax:
            return jsonify({"success": True, "message": "AWS credentials deleted successfully."}), 200
        flash("AWS credentials deleted successfully.", "success")
        return redirect(url_for('aws_s3.aws_s3_page'))
    except Exception as e:
        ub.session.rollback()
        log.error(f"Failed to delete AWS credentials: {e}")
        if is_ajax:
            return jsonify({"success": False, "message": "Database error while deleting credentials."}), 500
        flash("Database error while deleting credentials.", "error")
        return redirect(url_for('aws_s3.aws_s3_page'))


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
    Accepts both JSON (AJAX) and HTML form submissions.
    """
    is_ajax = request.is_json or request.headers.get('X-CSRFToken')
    data = request.get_json(silent=True) or {}
    if not data and request.form:
        data = request.form.to_dict()

    # Prefer credentials from request body; fallback to stored record
    access_key = data.get("aws_access_key_id", "").strip()
    secret_key = data.get("aws_secret_access_key", "").strip()
    region = data.get("default_region", "").strip()
    bucket_name = data.get("bucket_name", "").strip()
    log.info(f"Testing AWS connection (access_key={'****' + access_key[-4:] if access_key else 'from-store'}, region={region or 'from-store'}, bucket={bucket_name or 'from-store'})")

    if not (access_key and secret_key and region and bucket_name):
        record = _get_creds_record()
        if not record:
            if is_ajax:
                return jsonify({"success": False, "message": "No credentials provided or stored for testing connection."}), 400
            flash("No credentials provided or stored for testing connection.", "error")
            return redirect(url_for('aws_s3.aws_s3_page'))
        creds = _get_plain_creds(record)
        access_key = access_key or creds["access_key"]
        secret_key = secret_key or creds["secret_key"]
        region = region or creds["region"]
        bucket_name = bucket_name or creds["bucket"]

    if not (access_key and secret_key and region and bucket_name):
        if is_ajax:
            return jsonify({"success": False, "message": "Incomplete credentials for connection test."}), 400
        flash("Incomplete credentials for connection test.", "error")
        return redirect(url_for('aws_s3.aws_s3_page'))

    result = test_s3_connection(access_key, secret_key, region, bucket_name)
    status = 200 if result["success"] else 400
    if is_ajax:
        return jsonify(result), status
    # HTML form result — flash and redirect back to UI
    flash(result.get('message', 'Connection test completed.'), 'success' if result.get('success') else 'error')
    return redirect(url_for('aws_s3.aws_s3_page'))





# ---------------------------------------------------------------------------
# API – List bucket files
# ---------------------------------------------------------------------------

@aws_s3.route("/admin/aws-s3/files", methods=["GET"])
@admin_required
def list_files():
    """
    GET /admin/aws-s3/files?prefix=<optional>&max_keys=<optional>
    AJAX callers (X-CSRFToken header or Accept: application/json) receive JSON.
    Browser navigations receive a full page render.
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

    # AJAX / JSON request – return raw JSON
    is_ajax = request.is_json or request.headers.get('X-CSRFToken') or \
              'application/json' in request.headers.get('Accept', '')
    if is_ajax:
        return jsonify(result), status

    # Server-side render: normalise file list for template
    files = []
    if result.get('files'):
        for f in result['files']:
            size_raw = f.get('size', f.get('Size', 0))
            # Human-readable size
            size_human = f.get('SizeHuman', '')
            if not size_human:
                try:
                    b = int(size_raw)
                    if b < 1024:
                        size_human = f"{b} B"
                    elif b < 1048576:
                        size_human = f"{b/1024:.1f} KB"
                    else:
                        size_human = f"{b/1048576:.1f} MB"
                except (ValueError, TypeError):
                    size_human = str(size_raw)
            files.append({
                'key': f.get('key', f.get('Key', '')),
                'size_human': size_human,
                'last_modified': f.get('last_modified', f.get('LastModified', '')),
                'url': f.get('url', f.get('Url', '#')),
            })

    # Build credential dict for template (re-fetch to get fresh record)
    cred_record = _get_creds_record()
    credential = None
    if cred_record:
        credential = {
            'id': cred_record.id,
            'aws_access_key_id': '****' + (cred_record._masked_key() or ''),
            'default_region': cred_record.default_region,
            'default_output_format': cred_record.default_output_format,
            'bucket_name': cred_record.bucket_name,
            'created_at': cred_record.created_at.strftime('%Y-%m-%d %H:%M UTC') if cred_record.created_at else '',
            'updated_at': cred_record.updated_at.strftime('%Y-%m-%d %H:%M UTC') if cred_record.updated_at else '',
        }

    return render_template(
        'awsAdminPanel.html',
        credential=credential,
        regions=VALID_AWS_REGIONS,
        output_formats=VALID_OUTPUT_FORMATS,
        title='AWS S3 Configuration',
        page='aws-s3',
        files=files,
        prefix=prefix,
        truncated=result.get('truncated', False),
    )


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

    # accept JSON or form POST with _method=DELETE
    data = request.get_json(silent=True) or {}
    if not data and request.form:
        data = request.form.to_dict()
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
    if request.is_json:
        return jsonify(result), status
    flash(result.get('message', 'Delete completed.'), 'success' if result.get('success') else 'error')
    return redirect(url_for('aws_s3.aws_s3_page'))


# ---------------------------------------------------------------------------
# Form POST fallbacks for browsers (method-override via `_method`)
# ---------------------------------------------------------------------------

@aws_s3.route('/admin/aws-s3/credentials/<int:cred_id>', methods=['POST'])
@admin_required
def credentials_post(cred_id):
    """Handle form POSTs that carry `_method` for delete/update (HTML forms)."""
    method = request.form.get('_method', '').upper()
    if method == 'DELETE':
        return delete_credentials(cred_id)
    if method == 'PUT':
        # Build JSON-like dict from form and apply update
        data = request.form.to_dict()
        record = ub.session.query(AWSCredentials).filter(AWSCredentials.id == cred_id).first()
        if not record:
            flash('Credentials record not found.', 'error')
            return redirect(url_for('aws_s3.aws_s3_page'))
        # Build merged dict for validation
        # aws_access_key_id is stored as plain text; aws_secret_access_key is encrypted
        merged = {
            'aws_access_key_id': record.aws_access_key_id,
            'aws_secret_access_key': decrypt_value(record.aws_secret_access_key),
            'default_region': record.default_region,
            'default_output_format': record.default_output_format,
            'bucket_name': record.bucket_name,
        }
        for k in merged:
            if k in data and str(data[k]).strip():
                merged[k] = str(data[k]).strip()
        error = validate_credentials_payload(merged)
        if error:
            flash(error, 'error')
            return redirect(url_for('aws_s3.aws_s3_page'))
        try:
            # aws_access_key_id stored as plain text
            if 'aws_access_key_id' in data and str(data['aws_access_key_id']).strip():
                record.aws_access_key_id = str(data['aws_access_key_id']).strip()
            if 'aws_secret_access_key' in data and str(data['aws_secret_access_key']).strip():
                record.aws_secret_access_key = encrypt_value(str(data['aws_secret_access_key']).strip())
            if 'default_region' in data and str(data['default_region']).strip():
                record.default_region = str(data['default_region']).strip()
            if 'default_output_format' in data:
                record.default_output_format = str(data['default_output_format']).strip() or 'json'
            if 'bucket_name' in data and str(data['bucket_name']).strip():
                record.bucket_name = str(data['bucket_name']).strip()
            record.updated_at = datetime.datetime.utcnow()
            ub.session.commit()
            flash('AWS credentials updated successfully.', 'success')
            log.info(f"AWS credentials updated (id={cred_id}) by user '{current_user.name}'")
            return redirect(url_for('aws_s3.aws_s3_page'))
        except Exception as e:
            ub.session.rollback()
            log.error(f'Failed to update AWS credentials: {e}')
            flash('Database error while updating credentials.', 'error')
            return redirect(url_for('aws_s3.aws_s3_page'))
    return redirect(url_for('aws_s3.aws_s3_page'))


@aws_s3.route('/admin/aws-s3/files', methods=['POST'])
@admin_required
def files_post():
    """Handle form-based delete of files via `_method=DELETE` and key in form."""
    method = request.form.get('_method', '').upper()
    if method == 'DELETE':
        return delete_file()
    return redirect(url_for('aws_s3.aws_s3_page'))


@aws_s3.route('/admin/aws-s3/disconnect', methods=['POST', 'DELETE'])
@admin_required
def disconnect_post():
    """
    Disconnect / remove all stored AWS credentials.
    - POST with _method=DELETE  → HTML form fallback (browser forms)
    - DELETE (AJAX)             → JSON response for awsDisconnect() JS
    """
    is_ajax = request.method == 'DELETE' or request.is_json or request.headers.get('X-CSRFToken')
    try:
        record = _get_creds_record()
        if record:
            ub.session.delete(record)
            ub.session.commit()
            log.info(f"AWS credentials disconnected by user '{current_user.name}'")
            if is_ajax:
                return jsonify({"success": True, "message": "AWS disconnected successfully."}), 200
            flash('AWS disconnected successfully.', 'success')
        else:
            if is_ajax:
                return jsonify({"success": False, "message": "No AWS credentials configured."}), 404
            flash('No AWS credentials configured.', 'error')
    except Exception as e:
        ub.session.rollback()
        log.error(f'Failed to disconnect AWS: {e}')
        if is_ajax:
            return jsonify({"success": False, "message": "Failed to disconnect AWS."}), 500
        flash('Failed to disconnect AWS.', 'error')
    return redirect(url_for('aws_s3.aws_s3_page'))
