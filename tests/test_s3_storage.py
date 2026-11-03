# -*- coding: utf-8 -*-
"""
Unit tests for the S3 storage integration (cps/aws/*).

S3 is simulated with moto and metadata goes to an in-memory SQLite database,
so these tests touch neither AWS nor the application's PostgreSQL database.
"""

import io
import os
import struct
import zlib
from types import SimpleNamespace

import boto3
import pytest
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError
from moto import mock_aws
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from werkzeug.datastructures import FileStorage

import cps  # noqa: F401  (initialises the package)
from cps import ub
from cps.aws import s3Storage, storageSync, s3Config
from cps.aws.awsS3 import encrypt_value
from cps.aws.fileValidation import validate_upload, FileValidationError, clean_original_filename
from cps.aws.s3Storage import StorageError, translate_error, get_storage
from cps.models.awstbl import AWSCredentials
from cps.models.storedfile import StoredFile

BUCKET = "unit-test-bucket"


# --------------------------------------------------------------------------- helpers

def png_bytes(padding=0):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    raw = b"\x00\x00\x00\x00"
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)) + \
        chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    return png + b"\x00" * padding


MP4_BYTES = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 64
PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def upload(data, filename):
    return FileStorage(stream=io.BytesIO(data), filename=filename)


@pytest.fixture
def session(monkeypatch):
    engine = create_engine("sqlite://")
    StoredFile.__table__.create(engine)
    AWSCredentials.__table__.create(engine)
    sess = scoped_session(sessionmaker(bind=engine))
    monkeypatch.setattr(ub, "session", sess)
    yield sess
    sess.remove()


@pytest.fixture
def s3(monkeypatch, session, tmp_path):
    for name in ("AWS_S3_ENDPOINT_URL", "AWS_S3_PREFIX", "AWS_PROFILE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AWS_S3_ENABLED", "true")
    monkeypatch.setenv("AWS_S3_BUCKET", BUCKET)
    monkeypatch.setenv("AWS_S3_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setattr(storageSync.config, "get_book_path", lambda: str(tmp_path), raising=False)
    s3Storage._service_cache.clear()
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client
    s3Storage._service_cache.clear()


@pytest.fixture
def book(tmp_path):
    book = SimpleNamespace(id=7, path="Jane Doe/A Title (7)", has_cover=1,
                           data=[SimpleNamespace(name="A Title - Jane Doe", format="EPUB")])
    folder = tmp_path / book.path
    folder.mkdir(parents=True)
    (folder / "A Title - Jane Doe.epub").write_bytes(b"epub-content-v1")
    (folder / "cover.jpg").write_bytes(b"\xff\xd8\xff\xe0cover")
    return book


def keys(client):
    return sorted(o["Key"] for o in client.list_objects_v2(Bucket=BUCKET).get("Contents", []))


# --------------------------------------------------------------------------- configuration

def test_disabled_or_unconfigured_storage_is_none(monkeypatch, session):
    monkeypatch.setenv("AWS_S3_BUCKET", BUCKET)
    monkeypatch.setenv("AWS_S3_ENABLED", "false")
    assert get_storage() is None
    monkeypatch.setenv("AWS_S3_ENABLED", "true")
    monkeypatch.delenv("AWS_S3_BUCKET")
    assert get_storage() is None


def test_admin_credentials_take_precedence_and_secret_is_hidden(monkeypatch, session):
    monkeypatch.setenv("AWS_S3_ENABLED", "true")
    monkeypatch.setenv("AWS_S3_BUCKET", "env-bucket")
    session.add(AWSCredentials(aws_access_key_id="AKIAEXAMPLE", aws_secret_access_key=encrypt_value("s3cr3t-value"),
                               default_region="eu-west-1", default_output_format="json", bucket_name="admin-bucket"))
    session.commit()
    settings = s3Config.load_s3_settings()
    assert (settings.source, settings.bucket, settings.region) == ("admin", "admin-bucket", "eu-west-1")
    assert settings.secret_key == "s3cr3t-value"
    assert "s3cr3t-value" not in repr(settings) and "AKIAEXAMPLE" not in repr(settings)


def test_environment_settings(monkeypatch, session):
    monkeypatch.setenv("AWS_S3_ENABLED", "true")
    monkeypatch.setenv("AWS_S3_BUCKET", "env-bucket")
    monkeypatch.setenv("AWS_S3_REGION", "ap-south-1")
    monkeypatch.setenv("AWS_S3_PREFIX", "/prod/../app/")
    monkeypatch.setenv("AWS_S3_PRESIGNED_EXPIRY", "999999999")
    settings = s3Config.load_s3_settings()
    assert settings.source == "environment" and settings.access_key is None
    assert settings.prefix == "prod/app/"
    assert settings.presign_expiry == s3Config.MAX_PRESIGN_EXPIRY


# --------------------------------------------------------------------------- object keys

def test_object_keys_are_unique_and_safe(s3):
    storage = get_storage()
    key = storage.build_key("books", [7], "epub")
    assert key.startswith("books/7/") and key.endswith(".epub")
    assert key != storage.build_key("books", [7], "epub")
    traversal = storage.build_key("images", ["../../etc", "Passwd"], "png")
    assert ".." not in traversal and traversal.startswith("images/etc/passwd/")
    with pytest.raises(ValueError):
        storage.build_key("images", [], "p/ng")
    with pytest.raises(ValueError):
        storage.build_key("secrets", [], "png")


# --------------------------------------------------------------------------- validation

@pytest.mark.parametrize("data,filename,category", [
    (png_bytes(), "photo.PNG", "images"),
    (MP4_BYTES, "clip.mp4", "videos"),
    (PDF_BYTES, "manual.pdf", "documents"),
])
def test_valid_uploads_are_accepted(data, filename, category):
    info = validate_upload(upload(data, filename))
    assert info.category == category and info.size == len(data)


@pytest.mark.parametrize("data,filename,status", [
    (b"MZ\x90\x00 fake executable" * 10, "photo.png", 415),   # content does not match extension
    (b"MZ\x90\x00", "tool.exe", 415),                          # unsupported extension
    (b"", "empty.png", 400),
    (png_bytes(), "noextension", 400),
])
def test_invalid_uploads_are_rejected(data, filename, status):
    with pytest.raises(FileValidationError) as exc:
        validate_upload(upload(data, filename))
    assert exc.value.status == status


def test_size_limit_and_category_mismatch(monkeypatch):
    monkeypatch.setenv("AWS_S3_MAX_IMAGE_MB", "1")
    with pytest.raises(FileValidationError) as exc:
        validate_upload(upload(png_bytes(padding=2 * 1024 * 1024), "big.png"))
    assert exc.value.status == 413
    with pytest.raises(FileValidationError):
        validate_upload(upload(PDF_BYTES, "manual.pdf"), category="images")


def test_original_filename_is_cleaned():
    assert clean_original_filename("../../etc/passwd") == "passwd"
    assert clean_original_filename("C:\\Users\\x\\evil\x00.png") == "evil.png"
    assert clean_original_filename("...") == "file"


# --------------------------------------------------------------------------- book files

def test_mirror_book_format_records_metadata(s3, book, session):
    record = storageSync.mirror_book_format(book, book.data[0], user_id=3)
    assert record.entity_type == "book_format" and record.entity_id == "7" and record.variant == "EPUB"
    assert record.bucket == BUCKET and record.size_bytes == len(b"epub-content-v1")
    assert record.mime_type == "application/epub+zip" and record.uploaded_by == 3
    head = s3.head_object(Bucket=BUCKET, Key=record.object_key)
    assert head["ServerSideEncryption"] == "AES256"
    assert head["ContentType"] == "application/epub+zip"

    # unchanged file is not uploaded again
    assert storageSync.mirror_book_format(book, book.data[0]).id == record.id
    assert len(keys(s3)) == 1


def test_changed_file_replaces_previous_object(s3, book, session, tmp_path):
    first = storageSync.mirror_book_format(book, book.data[0])
    (tmp_path / book.path / "A Title - Jane Doe.epub").write_bytes(b"epub-content-version-2")
    second = storageSync.mirror_book_format(book, book.data[0])
    assert second.object_key != first.object_key
    assert keys(s3) == [second.object_key]
    assert session.query(StoredFile).count() == 1


def test_download_url_restore_and_delete(s3, book, session, tmp_path):
    record = storageSync.mirror_book_format(book, book.data[0])
    cover = storageSync.mirror_book_cover(book)
    assert cover.object_key.startswith("images/covers/7/")

    url = storageSync.book_download_url(book, book.data[0],
                                        {"Content-Disposition": "attachment; filename=a.epub",
                                         "Content-Type": "application/epub+zip"})
    assert BUCKET in url and "X-Amz-Signature" in url and "response-content-disposition" in url

    local = tmp_path / book.path / "A Title - Jane Doe.epub"
    local.unlink()
    (tmp_path / book.path / "cover.jpg").unlink()
    assert storageSync.restore_book_format(book, book.data[0]) is True
    assert local.read_bytes() == b"epub-content-v1"
    assert storageSync.restore_book_cover(book) is True

    assert storageSync.delete_book_files(book.id) == []
    assert keys(s3) == [] and session.query(StoredFile).count() == 0
    assert record.object_key not in keys(s3)
    # nothing left to restore from
    local.unlink()
    assert storageSync.restore_book_format(book, book.data[0]) is False


def test_delete_single_format_keeps_others(s3, book, session, tmp_path):
    (tmp_path / book.path / "A Title - Jane Doe.pdf").write_bytes(PDF_BYTES)
    book.data.append(SimpleNamespace(name="A Title - Jane Doe", format="PDF"))
    for data in book.data:
        storageSync.mirror_book_format(book, data)
    assert storageSync.delete_book_files(book.id, "pdf") == []
    remaining = session.query(StoredFile).all()
    assert [r.variant for r in remaining] == ["EPUB"] and keys(s3) == [remaining[0].object_key]


def test_object_removed_when_metadata_cannot_be_saved(s3, session, monkeypatch):
    storage = get_storage()
    monkeypatch.setattr(session, "commit", lambda: (_ for _ in ()).throw(RuntimeError("db down")))
    with pytest.raises(StorageError) as exc:
        storageSync.store_file(storage, io.BytesIO(PDF_BYTES), category="documents", scope=["uploads"],
                               extension="pdf", original_filename="a.pdf", mime_type="application/pdf")
    assert exc.value.code == "database_error"
    assert keys(s3) == []


def test_storage_unavailable_falls_back_to_local(monkeypatch, session, book, tmp_path):
    monkeypatch.setenv("AWS_S3_ENABLED", "false")
    monkeypatch.setattr(storageSync.config, "get_book_path", lambda: str(tmp_path), raising=False)
    assert storageSync.mirror_book_format(book, book.data[0]) is None
    assert storageSync.book_download_url(book, book.data[0]) is None
    assert storageSync.restore_book_format(book, book.data[0]) is False
    assert storageSync.delete_book_files(book.id) == []


# --------------------------------------------------------------------------- AWS errors

def test_missing_bucket_is_reported(s3, monkeypatch):
    monkeypatch.setenv("AWS_S3_BUCKET", "bucket-that-does-not-exist")
    storage = get_storage()
    result = storage.check_connection()
    assert result["success"] is False and result["code"] == "missing_bucket"
    with pytest.raises(StorageError) as exc:
        storage.upload_fileobj(io.BytesIO(b"x"), "documents/x.txt", "text/plain")
    assert exc.value.code == "missing_bucket"


def test_missing_object(s3):
    storage = get_storage()
    assert storage.object_exists("books/1/none.epub") is False
    storage.delete_object("books/1/none.epub")   # deleting a missing object is not an error
    with pytest.raises(StorageError) as exc:
        storage.download_to_path("books/1/none.epub", "/tmp/never-written-by-tests/x.epub")
    assert exc.value.code == "not_found"


@pytest.mark.parametrize("exc,code", [
    (NoCredentialsError(), "invalid_credentials"),
    (ClientError({"Error": {"Code": "InvalidAccessKeyId", "Message": "bad"}}, "PutObject"), "invalid_credentials"),
    (ClientError({"Error": {"Code": "SignatureDoesNotMatch", "Message": "bad"}}, "PutObject"), "invalid_credentials"),
    (ClientError({"Error": {"Code": "AccessDenied", "Message": "no"}}, "PutObject"), "access_denied"),
    (ClientError({"Error": {"Code": "NoSuchBucket", "Message": "no"}}, "PutObject"), "missing_bucket"),
    (ClientError({"Error": {"Code": "NoSuchKey", "Message": "no"}}, "GetObject"), "not_found"),
    (EndpointConnectionError(endpoint_url="https://s3.amazonaws.com"), "network_error"),
])
def test_error_translation(exc, code):
    err = translate_error(exc, "upload", BUCKET, "k")
    assert err.code == code
    assert "testing" not in err.message


def test_admin_switch_off_means_local_only(s3, monkeypatch, book):
    monkeypatch.setattr(s3Config.config, "aws_active", False, raising=False)
    assert s3Config.s3_enabled() is False and get_storage() is None
    assert storageSync.mirror_book_format(book, book.data[0]) is None
    assert keys(s3) == []
    monkeypatch.setattr(s3Config.config, "aws_active", True, raising=False)
    assert get_storage() is not None


# --------------------------------------------------------------------------- deletion / local copy tracking

def test_local_path_recorded_and_refreshed(s3, book, session, tmp_path):
    record = storageSync.mirror_book_format(book, book.data[0])
    cover = storageSync.mirror_book_cover(book)
    assert record.local_path == "Jane Doe/A Title (7)/A Title - Jane Doe.epub"
    assert cover.local_path == "Jane Doe/A Title (7)/cover.jpg"
    assert (tmp_path / record.local_path).read_bytes() == s3.get_object(Bucket=BUCKET, Key=record.object_key)["Body"].read()

    # title/author change moved the folder: keys stay, local paths follow
    (tmp_path / "New Author").mkdir()
    (tmp_path / book.path).rename(tmp_path / "New Author" / "A Title (7)")
    book.path = "New Author/A Title (7)"
    storageSync.refresh_local_paths(book)
    session.expire_all()
    assert session.query(StoredFile).filter_by(entity_type="book_format").one().local_path == \
        "New Author/A Title (7)/A Title - Jane Doe.epub"
    assert session.query(StoredFile).filter_by(entity_type="book_cover").one().object_key == cover.object_key


def test_remove_book_from_storage_deletes_objects_and_rows(s3, book, session):
    storageSync.mirror_book_now(book)
    assert len(keys(s3)) == 2
    assert storageSync.remove_book_from_storage(book.id) == (True, None)
    assert keys(s3) == [] and session.query(StoredFile).count() == 0


def test_remove_book_works_while_admin_switch_is_off(s3, book, session, monkeypatch):
    storageSync.mirror_book_now(book)
    monkeypatch.setattr(s3Config.config, "aws_active", False, raising=False)
    assert get_storage() is None                      # no new uploads ...
    assert storageSync.remove_book_from_storage(book.id) == (True, None)   # ... but cleanup works
    assert keys(s3) == [] and session.query(StoredFile).count() == 0


def test_remove_book_failure_keeps_everything(s3, book, session, monkeypatch):
    storageSync.mirror_book_now(book)

    def denied(self, key):
        raise StorageError("Access denied by AWS while trying to delete '{}'".format(key), "access_denied", 503)
    monkeypatch.setattr(s3Storage.S3StorageService, "delete_object", denied)
    ok, message = storageSync.remove_book_from_storage(book.id)
    assert ok is False and "Access denied" in message
    assert len(keys(s3)) == 2 and session.query(StoredFile).count() == 2


def test_remove_book_without_s3_configuration_warns(s3, book, session, monkeypatch):
    storageSync.mirror_book_now(book)
    monkeypatch.setenv("AWS_S3_ENABLED", "false")
    ok, message = storageSync.remove_book_from_storage(book.id)
    assert ok is True and "could not be removed from S3" in message
    assert session.query(StoredFile).count() == 2        # still tracked for the next library sync


def test_remove_single_format_only(s3, book, session, tmp_path):
    (tmp_path / book.path / "A Title - Jane Doe.pdf").write_bytes(PDF_BYTES)
    book.data.append(SimpleNamespace(name="A Title - Jane Doe", format="PDF"))
    storageSync.mirror_book_now(book)
    assert storageSync.remove_book_from_storage(book.id, "pdf") == (True, None)
    assert sorted(r.entity_type + ":" + (r.variant or "") for r in session.query(StoredFile)) == \
        ["book_cover:", "book_format:EPUB"]
    assert len(keys(s3)) == 2


@pytest.mark.parametrize("entity_type,entity_id,key", [
    ("book_format", "7", "books/8/0123456789abcdef0123456789abcdef.epub"),   # another book
    ("book_format", "7", "images/covers/7/0123456789abcdef0123456789abcdef.jpg"),
    ("book_format", "7", "checkingAWS.txt"),                                     # unrelated object
    ("book_format", "7", "books/7/../../checkingAWS.txt"),
    ("upload", None, "IMG20260119095746 (1).jpg"),
])
def test_unrelated_objects_are_never_deleted(s3, session, entity_type, entity_id, key):
    s3.put_object(Bucket=BUCKET, Key=key, Body=b"keep me")
    record = StoredFile(original_filename="x", object_key=key, bucket=BUCKET, category="books",
                        mime_type="application/octet-stream", size_bytes=7, entity_type=entity_type,
                        entity_id=entity_id)
    session.add(record)
    session.commit()
    errors = storageSync.delete_records(get_storage(), [record])
    assert errors and "Refusing" in errors[0]
    assert key in keys(s3) and session.query(StoredFile).count() == 1


def test_keys_built_by_the_app_pass_the_guard(s3, monkeypatch):
    monkeypatch.setenv("AWS_S3_PREFIX", "prod/app")
    storage = get_storage()
    for entity_type, entity_id, category, scope in [
            ("book_format", "12", "books", [12]), ("book_cover", "12", "images", ["covers", 12]),
            ("author_image", "3", "images", ["authors", 3]), ("forum_avatar", "5", "images", ["avatars", 5]),
            ("upload", None, "videos", storage.dated_scope("uploads", "u5"))]:
        record = StoredFile(object_key=storage.build_key(category, scope, "bin"), entity_type=entity_type,
                            entity_id=entity_id)
        assert storageSync.key_belongs_to_record(record), record.object_key


def test_mirror_book_now_switch_off_and_failure(s3, book, session, monkeypatch):
    monkeypatch.setattr(s3Config.config, "aws_active", False, raising=False)
    assert storageSync.mirror_book_now(book) == [] and keys(s3) == []
    monkeypatch.setattr(s3Config.config, "aws_active", True, raising=False)
    monkeypatch.setenv("AWS_S3_BUCKET", "bucket-that-does-not-exist")
    errors = storageSync.mirror_book_now(book)
    assert errors and "does not exist" in errors[0]
    assert session.query(StoredFile).count() == 0
