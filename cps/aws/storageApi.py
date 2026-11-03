# -*- coding: utf-8 -*-
"""
Storage API Blueprint - generic image / video / document uploads to AWS S3.

  POST   /api/storage/files                 upload one or more files (field "file")
  GET    /api/storage/files                 list own uploads (?all=1 for admins)
  GET    /api/storage/files/<id>            metadata + short-lived presigned URL
  GET    /api/storage/files/<id>/download   redirect to a presigned download URL
  DELETE /api/storage/files/<id>            delete object and metadata

Users need the upload role to upload; files can only be read or deleted by
their uploader or an admin. Book files, covers and author images are managed
through their existing routes and can only be accessed here by admins.
"""

import re
from functools import wraps

from flask import Blueprint, request, jsonify, redirect, abort, make_response

from ..cw_login import current_user
from .. import ub, logger
from ..usermanagement import user_login_required
from ..models.storedfile import StoredFile
from .s3Storage import StorageError, get_storage
from .fileValidation import validate_upload, FileValidationError, ALLOWED_TYPES
from . import storageSync

log = logger.create()

storage_api = Blueprint("storage_api", __name__, url_prefix="/api/storage")

_FILE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_ENTITY_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
MAX_FILES_PER_REQUEST = 10


def _error(message, status, code=None):
    payload = {"success": False, "message": message}
    if code:
        payload["code"] = code
    return make_response(jsonify(payload), status)


def _registered_user_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.is_anonymous:
            return _error("Login required", 401)
        return f(*args, **kwargs)
    return decorated


def _storage_or_503():
    storage = get_storage()
    if storage is None:
        abort(_error("AWS S3 storage is not configured", 503, "not_configured"))
    return storage


def _get_accessible_record(file_id) -> StoredFile:
    if not _FILE_ID_RE.match(file_id or ""):
        abort(_error("File not found", 404))
    record = ub.session.query(StoredFile).filter(StoredFile.file_uuid == file_id).first()
    if record is None:
        abort(_error("File not found", 404))
    if current_user.role_admin():
        return record
    # Non-admins only reach their own generic uploads; same 404 to avoid leaking existence
    if record.entity_type != storageSync.UPLOAD or record.uploaded_by != current_user.id:
        abort(_error("File not found", 404))
    return record


def _presigned_for(storage, record: StoredFile, inline: bool) -> str:
    return storageSync._service_for_record(storage, record).presigned_url(
        record.object_key, download_name=record.original_filename,
        content_type=record.mime_type, inline=inline)


@storage_api.route("/files", methods=["POST"])
@user_login_required
@_registered_user_required
def upload_files():
    if not current_user.role_upload() and not current_user.role_admin():
        return _error("You are not allowed to upload files", 403)
    files = [f for f in request.files.getlist("file") if f and f.filename]
    if not files:
        return _error("No file was uploaded (form field 'file')", 400)
    if len(files) > MAX_FILES_PER_REQUEST:
        return _error("At most {} files can be uploaded at once".format(MAX_FILES_PER_REQUEST), 400)

    category = request.form.get("category") or None
    if category and category not in ALLOWED_TYPES:
        return _error("Unknown category '{}'".format(category), 400)
    entity_id = request.form.get("entity_id") or None
    if entity_id and not _ENTITY_ID_RE.match(entity_id):
        return _error("Invalid entity_id", 400)

    # Validate everything before uploading anything
    validated = []
    for f in files:
        try:
            validated.append((f, validate_upload(f, category)))
        except FileValidationError as e:
            return _error("{}: {}".format(f.filename[:100], e.message), e.status, "invalid_file")

    storage = _storage_or_503()
    stored, failed = [], []
    for f, info in validated:
        try:
            record = storageSync.store_file(
                storage, f.stream, category=info.category,
                scope=storage.dated_scope("uploads", "u{}".format(current_user.id)),
                extension=info.extension, original_filename=info.original_filename,
                mime_type=info.mime_type, entity_type=storageSync.UPLOAD, entity_id=entity_id,
                user_id=current_user.id)
            stored.append(record.to_dict())
            log.info("User '%s' uploaded %s (%s, %d bytes) as %s", current_user.name,
                     info.original_filename, info.mime_type, info.size, record.file_uuid)
        except StorageError as e:
            failed.append({"filename": info.original_filename, "message": e.message, "code": e.code,
                           "status": e.status})

    if not stored:
        first = failed[0]
        return jsonify({"success": False, "message": first["message"], "code": first["code"],
                        "files": [], "errors": failed}), first["status"]
    return jsonify({"success": not failed, "files": stored, "errors": failed}), 201


@storage_api.route("/files", methods=["GET"])
@user_login_required
@_registered_user_required
def list_files():
    query = ub.session.query(StoredFile)
    if not (current_user.role_admin() and request.args.get("all") == "1"):
        query = query.filter(StoredFile.entity_type == storageSync.UPLOAD) \
                     .filter(StoredFile.uploaded_by == current_user.id)
    if request.args.get("category"):
        query = query.filter(StoredFile.category == request.args["category"])
    if request.args.get("entity_id"):
        query = query.filter(StoredFile.entity_id == request.args["entity_id"])
    try:
        limit = min(max(int(request.args.get("limit", 50)), 1), 200)
        offset = max(int(request.args.get("offset", 0)), 0)
    except ValueError:
        return _error("limit and offset must be integers", 400)
    total = query.count()
    records = query.order_by(StoredFile.created_at.desc(), StoredFile.id.desc()).offset(offset).limit(limit).all()
    return jsonify({"success": True, "total": total, "files": [r.to_dict() for r in records]})


@storage_api.route("/files/<file_id>", methods=["GET"])
@user_login_required
@_registered_user_required
def get_file(file_id):
    record = _get_accessible_record(file_id)
    storage = _storage_or_503()
    try:
        url = _presigned_for(storage, record, inline=record.category in ("images", "videos"))
    except StorageError as e:
        return _error(e.message, e.status, e.code)
    payload = record.to_dict()
    payload.update({"url": url, "url_expires_in": storage.settings.presign_expiry})
    return jsonify({"success": True, "file": payload})


@storage_api.route("/files/<file_id>/download", methods=["GET"])
@user_login_required
@_registered_user_required
def download_file(file_id):
    record = _get_accessible_record(file_id)
    storage = _storage_or_503()
    try:
        return redirect(_presigned_for(storage, record, inline=False), code=302)
    except StorageError as e:
        return _error(e.message, e.status, e.code)


@storage_api.route("/files/<file_id>", methods=["DELETE"])
@user_login_required
@_registered_user_required
def delete_file(file_id):
    record = _get_accessible_record(file_id)
    if not current_user.role_admin() and not current_user.role_upload():
        return _error("You are not allowed to delete files", 403)
    errors = storageSync.delete_records(get_storage(), [record])
    if errors:
        return _error(errors[0], 502, "delete_failed")
    log.info("User '%s' deleted stored file %s", current_user.name, file_id)
    return jsonify({"success": True, "message": "File deleted"})
