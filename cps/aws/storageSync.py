# -*- coding: utf-8 -*-
"""
Upload service connecting application files to S3 objects and their
`stored_files` metadata rows.

The local Calibre library stays the working copy (converter, readers, e-mail
and Kobo sync read it directly). Every stored file is mirrored to S3, which
then serves downloads through presigned URLs and restores local copies that
went missing. Every function here is a no-op when S3 storage is not
configured, so behaviour without S3 is unchanged.
"""

import os
import re
import mimetypes
import dataclasses
from typing import Optional, List, Tuple

from .. import logger, ub, config
from .. import file_helper  # noqa: F401  (registers ebook mimetypes)
from ..models.storedfile import StoredFile
from .s3Storage import S3StorageService, StorageError, get_storage

log = logger.create()

BOOK_FORMAT = "book_format"
BOOK_COVER = "book_cover"
AUTHOR_IMAGE = "author_image"
FORUM_AVATAR = "forum_avatar"
UPLOAD = "upload"

ANY_VARIANT = object()


def _session(session):
    return session if session is not None else ub.session


def content_type_for(filename: str) -> str:
    return mimetypes.types_map.get(os.path.splitext(filename)[1].lower(), "application/octet-stream")


# --------------------------------------------------------------------------- records

def find_records(entity_type: str, entity_id, variant=ANY_VARIANT, session=None) -> List[StoredFile]:
    query = _session(session).query(StoredFile) \
        .filter(StoredFile.entity_type == entity_type) \
        .filter(StoredFile.entity_id == str(entity_id))
    if variant is not ANY_VARIANT:
        query = query.filter(StoredFile.variant == variant)
    return query.order_by(StoredFile.created_at.desc(), StoredFile.id.desc()).all()


def find_record(entity_type: str, entity_id, variant=None, session=None) -> Optional[StoredFile]:
    records = find_records(entity_type, entity_id, variant, session)
    return records[0] if records else None


def _service_for_record(storage: S3StorageService, record: StoredFile) -> S3StorageService:
    """Objects written before the bucket was changed still need to be reachable for deletion/restore."""
    if record.bucket == storage.bucket:
        return storage
    return S3StorageService(dataclasses.replace(storage.settings, bucket=record.bucket))


def store_file(storage: S3StorageService, source, *, category: str, scope, extension: str,
               original_filename: str, mime_type: str, entity_type: str = UPLOAD, entity_id=None,
               variant: Optional[str] = None, user_id: Optional[int] = None,
               replace: bool = True, local_path: Optional[str] = None, session=None) -> StoredFile:
    """
    Upload `source` (a filesystem path or a binary file object) and record its metadata.
    With replace=True, older objects for the same entity/variant are removed afterwards.
    Raises StorageError; nothing is left behind in S3 if the metadata cannot be saved.
    """
    sess = _session(session)
    key = storage.build_key(category, scope, extension)
    if isinstance(source, (str, os.PathLike)):
        result = storage.upload_path(source, key, mime_type, original_filename)
    else:
        result = storage.upload_fileobj(source, key, mime_type, original_filename)

    record = StoredFile(
        original_filename=original_filename[:255],
        object_key=key,
        bucket=storage.bucket,
        storage_provider="s3",
        local_path=local_path,
        category=category,
        mime_type=mime_type,
        size_bytes=result.get("size", 0),
        etag=result.get("etag"),
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        variant=variant,
        uploaded_by=user_id,
    )
    try:
        sess.add(record)
        sess.commit()
    except Exception as e:
        sess.rollback()
        log.error("Saving metadata for s3 object %s failed: %s", key, e)
        try:
            storage.delete_object(key)
        except StorageError:
            log.error("Could not remove orphaned S3 object %s", key)
        raise StorageError("Saving file metadata failed", "database_error", 500)

    if replace and entity_id is not None and entity_type != UPLOAD:
        older = [r for r in find_records(entity_type, entity_id, variant, sess) if r.id != record.id]
        delete_records(storage, older, sess)
    return record


_OBJECT_NAME = r"[0-9a-f]{32}(?:\.[a-z0-9]{1,10})?"
_ROOT_PREFIX = r"(?:[A-Za-z0-9._-]+/)*"
_ENTITY_SCOPES = {
    BOOK_FORMAT: "books/{}/",
    BOOK_COVER: "images/covers/{}/",
    AUTHOR_IMAGE: "images/authors/{}/",
    FORUM_AVATAR: "images/avatars/{}/",
}


def key_belongs_to_record(record: StoredFile) -> bool:
    """
    True if the object key has the layout build_key() creates for this record's entity,
    e.g. books/12/<uuid>.pdf for book 12. Guards against deleting unrelated objects
    because of a corrupted or hand-edited metadata row.
    """
    key = record.object_key or ""
    if record.entity_type in _ENTITY_SCOPES:
        if not record.entity_id:
            return False
        scope = re.escape(_ENTITY_SCOPES[record.entity_type].format(str(record.entity_id).lower()))
    elif record.entity_type == UPLOAD:
        scope = r"(?:images|videos|documents)/uploads/u\d+/\d{4}/\d{2}/"
    else:
        return False
    return re.fullmatch(_ROOT_PREFIX + scope + _OBJECT_NAME, key) is not None


def delete_records(storage: Optional[S3StorageService], records: List[StoredFile], session=None) -> List[str]:
    """Delete objects and their metadata. Rows whose object could not be deleted are kept for a later retry."""
    if not records:
        return []
    sess = _session(session)
    if storage is None:
        return ["AWS S3 is not configured; {} stored file(s) could not be removed".format(len(records))]
    errors = []
    for record in records:
        if not key_belongs_to_record(record):
            log.error("Refusing to delete s3://%s/%s: key does not belong to %s %s",
                      record.bucket, record.object_key, record.entity_type, record.entity_id)
            errors.append("Refusing to delete S3 object '{}': it does not belong to {} {}".format(
                record.object_key, record.entity_type, record.entity_id))
            continue
        try:
            _service_for_record(storage, record).delete_object(record.object_key)
            sess.delete(record)
        except StorageError as e:
            errors.append(e.message)
    try:
        sess.commit()
    except Exception as e:
        sess.rollback()
        log.error("Removing stored file metadata failed: %s", e)
        errors.append("Removing stored file metadata failed")
    return errors


def delete_entity_files(entity_type: str, entity_id, variant=ANY_VARIANT, session=None) -> List[str]:
    try:
        records = find_records(entity_type, entity_id, variant, session)
    except Exception as e:
        log.error("Looking up stored files for %s %s failed: %s", entity_type, entity_id, e)
        return ["Looking up stored files failed"]
    if not records:
        return []
    return delete_records(get_storage(session, for_cleanup=True), records, session)


# --------------------------------------------------------------------------- books

def local_book_file(book, data) -> str:
    return os.path.join(config.get_book_path(), book.path, data.name + "." + data.format.lower())


def local_cover_file(book) -> str:
    return os.path.join(config.get_book_path(), book.path, "cover.jpg")


def library_relative_path(path: str) -> str:
    """Path inside the local library folder, as stored in stored_files.local_path."""
    return os.path.relpath(path, config.get_book_path()).replace("\\", "/")


def _mirror(storage, path, record, force, **kwargs) -> Optional[StoredFile]:
    if not os.path.isfile(path):
        log.warning("Not mirroring %s to S3: local file missing", path)
        return None
    if record and not force and record.size_bytes == os.path.getsize(path):
        return record
    return store_file(storage, path, local_path=library_relative_path(path), **kwargs)


def mirror_book_format(book, data, user_id=None, force=False, storage=None, session=None) -> Optional[StoredFile]:
    storage = storage or get_storage(session)
    if storage is None:
        return None
    fmt = data.format.upper()
    path = local_book_file(book, data)
    return _mirror(storage, path, find_record(BOOK_FORMAT, book.id, fmt, session), force,
                   category="books", scope=[book.id], extension=fmt.lower(),
                   original_filename=os.path.basename(path), mime_type=content_type_for(path),
                   entity_type=BOOK_FORMAT, entity_id=book.id, variant=fmt, user_id=user_id, session=session)


def mirror_book_cover(book, user_id=None, force=False, storage=None, session=None) -> Optional[StoredFile]:
    storage = storage or get_storage(session)
    if storage is None or not book.has_cover:
        return None
    return _mirror(storage, local_cover_file(book), find_record(BOOK_COVER, book.id, None, session), force,
                   category="images", scope=["covers", book.id], extension="jpg",
                   original_filename="cover.jpg", mime_type="image/jpeg",
                   entity_type=BOOK_COVER, entity_id=book.id, user_id=user_id, session=session)


def mirror_book_now(book, formats=None, include_cover=True, user_id=None) -> List[str]:
    """
    Copy a book that was just saved to the local library folder to S3, in the current request.
    formats=None mirrors every format. Returns user-facing error messages (empty on success
    or when S3 storage is switched off - the local copy is then the only copy).
    """
    try:
        storage = get_storage()
    except Exception as e:
        log.error("Could not read S3 configuration: %s", e)
        return ["Could not read the AWS S3 configuration"]
    if storage is None:
        return []
    errors = []
    for data in book.data:
        if formats is not None and data.format.upper() not in [f.upper() for f in formats]:
            continue
        try:
            if mirror_book_format(book, data, user_id=user_id, force=True, storage=storage) is None:
                errors.append("{} file is missing in the local library folder".format(data.format.upper()))
        except StorageError as e:
            errors.append(e.message)
    if include_cover and book.has_cover:
        try:
            mirror_book_cover(book, user_id=user_id, force=True, storage=storage)
        except StorageError as e:
            errors.append(e.message)
    return errors


def refresh_local_paths(book, session=None) -> None:
    """Keep stored_files.local_path in step after a title/author change moved the book's folder."""
    try:
        sess = _session(session)
        changed = False
        formats = {d.format.upper(): d for d in book.data}
        for record in find_records(BOOK_FORMAT, book.id, ANY_VARIANT, sess):
            data = formats.get((record.variant or "").upper())
            if data is not None:
                new_path = library_relative_path(local_book_file(book, data))
                changed |= record.local_path != new_path
                record.local_path = new_path
        for record in find_records(BOOK_COVER, book.id, ANY_VARIANT, sess):
            new_path = library_relative_path(local_cover_file(book))
            changed |= record.local_path != new_path
            record.local_path = new_path
        if changed:
            sess.commit()
    except Exception as e:
        _session(session).rollback()
        log.error("Updating local paths of book %s failed: %s", getattr(book, "id", "?"), e)


def book_storage_records(book_id, book_format: Optional[str] = None, session=None) -> List[StoredFile]:
    if book_format:
        return find_records(BOOK_FORMAT, book_id, book_format.upper(), session)
    return find_records(BOOK_FORMAT, book_id, ANY_VARIANT, session) + \
        find_records(BOOK_COVER, book_id, ANY_VARIANT, session)


def remove_book_from_storage(book_id, book_format: Optional[str] = None,
                             session=None) -> Tuple[bool, Optional[str]]:
    """
    S3 part of deleting a book (or one format). Must run BEFORE the local files and
    database rows are removed, so a failure leaves the book completely intact.

    Uses the stored bucket/object key of every tracked file - never a key derived
    from the book path. Returns:
      (True, None)     nothing stored in S3, or all objects deleted -> continue deleting
      (True, warning)  S3 is not configured any more; objects stay tracked for a later
                       library sync -> continue deleting, show the warning
      (False, error)   an S3 deletion failed -> abort, the book must not be deleted
    """
    try:
        records = book_storage_records(book_id, book_format, session)
    except Exception as e:
        _session(session).rollback()
        log.error("Looking up S3 files of book %s failed: %s", book_id, e)
        return False, "Could not look up the book's files in S3 storage"
    if not records:
        return True, None
    storage = get_storage(session, for_cleanup=True)
    if storage is None:
        log.warning("Book %s deleted while S3 is not configured; %d S3 object(s) remain tracked",
                    book_id, len(records))
        return True, "AWS S3 is not configured, so {} file(s) of this book could not be removed from S3. " \
                     "They are removed by the next library sync.".format(len(records))
    errors = delete_records(storage, records, session)
    if errors:
        log.error("Deleting S3 files of book %s failed: %s", book_id, "; ".join(errors))
        return False, errors[0]
    log.info("Deleted %d S3 object(s) of book %s%s", len(records), book_id,
             " format " + book_format.upper() if book_format else "")
    return True, None


def delete_book_files(book_id, book_format: Optional[str] = None, session=None) -> List[str]:
    """Remove a book's objects from S3 (one format, or every format plus the cover)."""
    if book_format:
        return delete_entity_files(BOOK_FORMAT, book_id, book_format.upper(), session)
    return delete_entity_files(BOOK_FORMAT, book_id, ANY_VARIANT, session) + \
        delete_entity_files(BOOK_COVER, book_id, ANY_VARIANT, session)


def _restore(entity_type, entity_id, variant, dest_path, session=None) -> bool:
    try:
        storage = get_storage(session)
        if storage is None:
            return False
        record = find_record(entity_type, entity_id, variant, session)
        if record is None:
            return False
        _service_for_record(storage, record).download_to_path(record.object_key, dest_path)
        log.info("Restored %s from s3://%s/%s", dest_path, record.bucket, record.object_key)
        return True
    except StorageError as e:
        log.error("Restoring %s from S3 failed: %s", dest_path, e.message)
    except Exception as e:
        log.error("Restoring %s from S3 failed: %s", dest_path, e)
    return False


def restore_book_format(book, data) -> bool:
    """Download a book file from S3 when its local copy is missing. Returns True if restored."""
    return _restore(BOOK_FORMAT, book.id, data.format.upper(), local_book_file(book, data))


def restore_book_cover(book) -> bool:
    return _restore(BOOK_COVER, book.id, None, local_cover_file(book))


def book_download_url(book, data, headers=None) -> Optional[str]:
    """Presigned S3 URL for a book download, or None to serve it locally."""
    try:
        storage = get_storage()
        if storage is None or not storage.settings.serve_downloads:
            return None
        record = find_record(BOOK_FORMAT, book.id, data.format.upper())
        if record is None:
            return None
        local_path = local_book_file(book, data)
        if os.path.isfile(local_path) and os.path.getsize(local_path) != record.size_bytes:
            return None   # local file changed and its S3 copy is not updated yet
        headers = headers or {}
        return _service_for_record(storage, record).presigned_url(
            record.object_key,
            content_type=headers.get("Content-Type"),
            content_disposition=headers.get("Content-Disposition"),
            download_name=record.original_filename)
    except StorageError as e:
        log.warning("Falling back to local download for book %s: %s", book.id, e.message)
    except Exception as e:
        log.warning("Falling back to local download for book %s: %s", book.id, e)
    return None


# --------------------------------------------------------------------------- images

def mirror_image(entity_type: str, entity_id, path: str, scope_name: str, user_id=None) -> Optional[str]:
    """
    Mirror a locally saved image (author image, forum avatar) to S3, replacing the previous one.
    Returns None on success or when S3 is not configured, otherwise a warning message.
    """
    try:
        storage = get_storage()
        if storage is None:
            return None
        extension = os.path.splitext(path)[1].lower().lstrip(".")
        store_file(storage, path, category="images", scope=[scope_name, entity_id], extension=extension,
                   original_filename=os.path.basename(path), mime_type=content_type_for(path),
                   entity_type=entity_type, entity_id=entity_id, user_id=user_id)
        return None
    except StorageError as e:
        return "Image saved locally, but uploading it to S3 failed: {}".format(e.message)
    except Exception as e:
        log.error("Mirroring %s to S3 failed: %s", path, e)
        return "Image saved locally, but uploading it to S3 failed"
