# -*- coding: utf-8 -*-
"""
Upload validation for files sent to S3 storage.

Every upload is checked on the backend for:
  * an allowed extension for its category (images / videos / documents)
  * a sniffed MIME type (python-magic, file content - not the client header)
    that matches the extension
  * a per-category size limit (configurable through environment variables)
"""

import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from .. import logger
from .s3Config import env_int

log = logger.create()

try:
    import magic
    _magic_error = None
except ImportError as e:
    magic = None
    _magic_error = "python-magic is not installed: {}".format(e)

MB = 1024 * 1024

# extension -> sniffed MIME types accepted for it
ALLOWED_TYPES = {
    "images": {
        "jpg": {"image/jpeg"},
        "jpeg": {"image/jpeg"},
        "png": {"image/png"},
        "gif": {"image/gif"},
        "webp": {"image/webp"},
        "bmp": {"image/bmp", "image/x-ms-bmp"},
    },
    "videos": {
        "mp4": {"video/mp4"},
        "m4v": {"video/mp4", "video/x-m4v"},
        "webm": {"video/webm"},
        "mov": {"video/quicktime"},
        "mkv": {"video/x-matroska"},
        "avi": {"video/x-msvideo", "video/avi"},
    },
    "documents": {
        "pdf": {"application/pdf"},
        "epub": {"application/epub+zip", "application/zip"},
        "txt": {"text/plain"},
        "md": {"text/plain", "text/markdown"},
        "csv": {"text/csv", "text/plain"},
        "rtf": {"text/rtf", "application/rtf"},
        "doc": {"application/msword", "application/CDFV2"},
        "docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/zip"},
        "odt": {"application/vnd.oasis.opendocument.text", "application/zip"},
        "mobi": {"application/x-mobipocket-ebook"},
        "azw3": {"application/x-mobipocket-ebook", "application/octet-stream"},
        "fb2": {"text/xml", "application/xml"},
    },
}

# canonical Content-Type stored in S3 / the database for each extension
CONTENT_TYPES = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "gif": "image/gif",
    "webp": "image/webp", "bmp": "image/bmp",
    "mp4": "video/mp4", "m4v": "video/x-m4v", "webm": "video/webm", "mov": "video/quicktime",
    "mkv": "video/x-matroska", "avi": "video/x-msvideo",
    "pdf": "application/pdf", "epub": "application/epub+zip", "txt": "text/plain",
    "md": "text/markdown", "csv": "text/csv", "rtf": "application/rtf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "odt": "application/vnd.oasis.opendocument.text", "mobi": "application/x-mobipocket-ebook",
    "azw3": "application/vnd.amazon.ebook", "fb2": "application/x-fictionbook+xml",
}

_DEFAULT_LIMITS_MB = {"images": 10, "videos": 500, "documents": 100}


class FileValidationError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message = message
        self.status = status


@dataclass
class ValidatedFile:
    category: str
    extension: str
    mime_type: str
    size: int
    original_filename: str


def max_size_bytes(category: str) -> int:
    default_mb = _DEFAULT_LIMITS_MB[category]
    return env_int("AWS_S3_MAX_{}_MB".format(category.rstrip("s").upper()), default_mb, 1) * MB


def category_for_extension(extension: str) -> Optional[str]:
    for category, types in ALLOWED_TYPES.items():
        if extension in types:
            return category
    return None


def clean_original_filename(filename: str) -> str:
    """Strip any path, control characters and excessive length from a client-supplied filename.
    The result is only stored as metadata - it never becomes part of an object key."""
    name = unicodedata.normalize("NFC", filename or "")
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip().lstrip(".")
    if len(name) > 255:
        root, ext = os.path.splitext(name)
        name = root[:255 - len(ext)] + ext
    return name or "file"


def get_extension(filename: str) -> str:
    name = clean_original_filename(filename)
    if "." not in name:
        return ""
    ext = name.rsplit(".", 1)[-1].lower()
    return ext if re.fullmatch(r"[a-z0-9]{1,10}", ext) else ""


def _stream_size(stream) -> int:
    pos = stream.tell()
    stream.seek(0, os.SEEK_END)
    size = stream.tell()
    stream.seek(pos)
    return size


def sniff_mime_type(stream) -> str:
    if magic is None:
        raise FileValidationError("File type detection is unavailable on the server", status=500)
    pos = stream.tell()
    stream.seek(0)
    head = stream.read(8192)
    stream.seek(pos)
    return magic.Magic(mime=True).from_buffer(head)


def validate_upload(file_storage, category: Optional[str] = None) -> ValidatedFile:
    """Validate a werkzeug FileStorage. Raises FileValidationError on rejection."""
    if file_storage is None or not file_storage.filename:
        raise FileValidationError("No file was uploaded")

    original = clean_original_filename(file_storage.filename)
    extension = get_extension(original)
    if not extension:
        raise FileValidationError("File must have a valid extension")

    detected_category = category_for_extension(extension)
    if detected_category is None or (category and category != detected_category):
        allowed = ALLOWED_TYPES.get(category) if category else None
        allowed_list = sorted(allowed) if allowed else sorted(e for t in ALLOWED_TYPES.values() for e in t)
        raise FileValidationError("File type '.{}' is not supported. Allowed: {}".format(
            extension, ", ".join(allowed_list)), status=415)
    category = detected_category

    stream = file_storage.stream
    size = _stream_size(stream)
    if size == 0:
        raise FileValidationError("Uploaded file is empty")
    limit = max_size_bytes(category)
    if size > limit:
        raise FileValidationError("File is too large ({:.1f} MB). Maximum for {} is {} MB".format(
            size / MB, category, limit // MB), status=413)

    sniffed = sniff_mime_type(stream)
    if sniffed not in ALLOWED_TYPES[category][extension]:
        log.warning("Rejected upload '%s': content type %s does not match extension .%s",
                    original, sniffed, extension)
        raise FileValidationError("File content does not match its '.{}' extension".format(extension), status=415)

    stream.seek(0)
    return ValidatedFile(category=category,
                         extension=extension,
                         mime_type=CONTENT_TYPES.get(extension, sniffed),
                         size=size,
                         original_filename=original)
