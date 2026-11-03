# -*- coding: utf-8 -*-
"""
End-to-end tests of the S3 integration through the real Flask routes.

Runs the complete application against the configured PostgreSQL database
(DATABASE_URL from .env) with S3 simulated by moto - no AWS calls are made.
Test users, books and files are created through the application and removed
again at the end. Skipped when the database is not reachable.
"""

import io
import os
import re
import time
import shutil
import struct
import tempfile
import zipfile
import zlib

import pytest

boto3 = pytest.importorskip("boto3")
from moto import mock_aws  # noqa: E402

BUCKET = "route-test-bucket"
PASSWORD = "S3-test-Passw0rd!"
BOOK_TITLE = "S3 Integration Test Book"

def _png():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0)) + \
        chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00\x00")) + chunk(b"IEND", b"")


PNG = _png()
MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 64
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def make_epub():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        z.writestr("META-INF/container.xml",
                   '<?xml version="1.0"?><container version="1.0" '
                   'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                   '<rootfile full-path="content.opf" media-type="application/oebps-package+xml"/>'
                   '</rootfiles></container>')
        z.writestr("content.opf",
                   '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="2.0" '
                   'unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
                   '<dc:title>{}</dc:title><dc:creator>S3 Test Author</dc:creator>'
                   '<dc:language>en</dc:language><dc:identifier id="id">s3-test-0001</dc:identifier>'
                   '</metadata><manifest><item id="c" href="c.html" media-type="application/xhtml+xml"/>'
                   '</manifest><spine><itemref idref="c"/></spine></package>'.format(BOOK_TITLE))
        z.writestr("c.html", "<html><body><p>Hello S3</p></body></html>")
    return buf.getvalue()


def _db_available():
    try:
        import psycopg2
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
        url = os.environ.get("DATABASE_URL", "").replace("postgresql+psycopg2", "postgresql")
        if not url:
            return False
        psycopg2.connect(url, connect_timeout=3).close()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_available(), reason="PostgreSQL database not reachable")


@pytest.fixture(scope="module")
def env():
    library = tempfile.mkdtemp(prefix="s3test-library-")
    saved_env = {k: os.environ.get(k) for k in ("AWS_S3_ENABLED", "AWS_S3_BUCKET", "AWS_S3_REGION",
                                                "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")}
    os.environ.update({"AWS_S3_ENABLED": "true", "AWS_S3_BUCKET": BUCKET, "AWS_S3_REGION": "us-east-1",
                       "AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing"})
    mock = mock_aws()
    mock.start()
    boto3.client("s3", region_name="us-east-1").create_bucket(Bucket=BUCKET)

    import cps
    from cps.aws import s3Config, s3Storage
    s3Storage._service_cache.clear()
    # use the environment configuration (moto bucket), never stored admin credentials
    original_admin = s3Config._settings_from_admin_record
    s3Config._settings_from_admin_record = lambda session: None

    app = cps.create_app()
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    # same blueprints cps.main.main() registers before starting the web server
    from cps.web import web
    from cps.admin import admi
    from cps.editbooks import editbook
    from cps.about import about
    from cps.search import search
    from cps.shelf import shelf
    from cps.tasks_status import tasks
    from cps.jinjia import jinjia
    from cps.error_handler import init_errorhandler
    init_errorhandler()
    for bp in (search, tasks, web, jinjia, about, shelf, admi, editbook):
        app.register_blueprint(bp)
    from cps import config, ub, constants, limiter
    if limiter:
        limiter.enabled = False
    config.get_book_path = lambda: library
    config.config_uploading = 1
    config.config_embed_metadata = False   # plain downloads (embedding via calibredb is not under test)
    config.config_upload_formats = ",".join(sorted(set(config.config_upload_formats.split(",")) | {"epub"}))

    from werkzeug.security import generate_password_hash
    roles = {
        "s3test_admin": constants.ROLE_ADMIN | constants.ROLE_UPLOAD | constants.ROLE_EDIT
        | constants.ROLE_DELETE_BOOKS | constants.ROLE_DOWNLOAD | constants.ROLE_VIEWER,
        "s3test_uploader": constants.ROLE_UPLOAD | constants.ROLE_DOWNLOAD | constants.ROLE_VIEWER,
        "s3test_reader": constants.ROLE_DOWNLOAD | constants.ROLE_VIEWER,
    }
    users = {}
    for name, role in roles.items():
        ub.session.query(ub.User).filter(ub.User.name == name).delete()
        user = ub.User(name=name, email=name + "@example.invalid", role=role,
                       password=generate_password_hash(PASSWORD))
        ub.session.add(user)
        ub.session.commit()
        users[name] = user.id

    yield {"app": app, "users": users, "library": library, "s3": boto3.client("s3", region_name="us-east-1")}

    from cps.models.storedfile import StoredFile
    ub.session.rollback()
    ub.session.query(StoredFile).filter(StoredFile.uploaded_by.in_(list(users.values()))).delete(
        synchronize_session=False)
    ub.session.query(ub.User_Sessions).filter(ub.User_Sessions.user_id.in_(list(users.values()))).delete(
        synchronize_session=False)
    ub.session.query(ub.User).filter(ub.User.id.in_(list(users.values()))).delete(synchronize_session=False)
    ub.session.commit()
    s3Config._settings_from_admin_record = original_admin
    mock.stop()
    # what server.stop() does on shutdown: the updater thread is not a daemon
    cps.updater_thread.stop()
    cps.web_server.shutdown_scheduler()
    shutil.rmtree(library, ignore_errors=True)
    for k, v in saved_env.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def client_for(env, name):
    client = env["app"].test_client()
    resp = client.post("/login", data={"username": name, "password": PASSWORD})
    assert resp.status_code == 302, "login failed for " + name
    return client


def s3_keys(env):
    return {o["Key"] for o in env["s3"].list_objects_v2(Bucket=BUCKET).get("Contents", [])}


def stored(entity_type, entity_id):
    from cps import ub
    from cps.models.storedfile import StoredFile
    ub.session.expire_all()
    return ub.session.query(StoredFile).filter(StoredFile.entity_type == entity_type,
                                               StoredFile.entity_id == str(entity_id)).all()


def wait_for(predicate, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        if predicate():
            return True
        time.sleep(0.5)
    return False


# --------------------------------------------------------------------------- generic storage API

def test_unauthenticated_upload_rejected(env):
    resp = env["app"].test_client().post("/api/storage/files",
                                         data={"file": (io.BytesIO(PNG), "a.png")})
    assert resp.status_code in (302, 401)
    assert not any("uploads" in k for k in s3_keys(env))


def test_user_without_upload_role_rejected(env):
    client = client_for(env, "s3test_reader")
    resp = client.post("/api/storage/files", data={"file": (io.BytesIO(PNG), "a.png")})
    assert resp.status_code == 403


def test_upload_retrieve_delete_image_video_document(env):
    client = client_for(env, "s3test_uploader")
    resp = client.post("/api/storage/files", content_type="multipart/form-data", data={
        "file": [(io.BytesIO(PNG), "photo.png"), (io.BytesIO(MP4), "clip.mp4"), (io.BytesIO(PDF), "doc.pdf")]})
    assert resp.status_code == 201, resp.get_json()
    files = resp.get_json()["files"]
    assert [f["category"] for f in files] == ["images", "videos", "documents"]

    from cps import ub
    from cps.models.storedfile import StoredFile
    records = {r.file_uuid: r for r in ub.session.query(StoredFile).filter(
        StoredFile.file_uuid.in_([f["id"] for f in files])).all()}
    assert len(records) == 3
    uploader_id = env["users"]["s3test_uploader"]
    object_keys = {}
    for f in files:
        r = records[f["id"]]
        assert r.bucket == BUCKET and r.storage_provider == "s3" and r.uploaded_by == uploader_id
        assert r.object_key.startswith("{}/uploads/u{}/".format(f["category"], uploader_id))
        assert r.object_key in s3_keys(env)
        object_keys[f["id"]] = r.object_key
        assert "bucket" not in f and "object_key" not in f   # bucket layout not exposed

    image = files[0]
    meta = client.get("/api/storage/files/" + image["id"]).get_json()["file"]
    assert "X-Amz-Signature" in meta["url"] and meta["mime_type"] == "image/png"
    dl = client.get("/api/storage/files/{}/download".format(image["id"]))
    assert dl.status_code == 302 and "X-Amz-Signature" in dl.headers["Location"]

    listing = client.get("/api/storage/files").get_json()
    assert {f["id"] for f in files} <= {f["id"] for f in listing["files"]}

    # other users can neither read nor delete the files
    other = client_for(env, "s3test_reader")
    assert other.get("/api/storage/files/" + image["id"]).status_code == 404
    assert other.delete("/api/storage/files/" + image["id"]).status_code == 404

    for f in files:
        assert client.delete("/api/storage/files/" + f["id"]).status_code == 200
        assert object_keys[f["id"]] not in s3_keys(env)
    assert client.get("/api/storage/files/" + image["id"]).status_code == 404


@pytest.mark.parametrize("data,name,status", [
    (b"MZ\x90\x00" * 50, "evil.png", 415),
    (b"MZ\x90\x00" * 50, "evil.exe", 415),
    (b"", "empty.pdf", 400),
])
def test_invalid_files_rejected(env, data, name, status):
    client = client_for(env, "s3test_uploader")
    before = s3_keys(env)
    resp = client.post("/api/storage/files", data={"file": (io.BytesIO(data), name)})
    assert resp.status_code == status
    assert s3_keys(env) == before


def test_bad_file_id_is_404(env):
    client = client_for(env, "s3test_uploader")
    assert client.get("/api/storage/files/../../etc/passwd").status_code == 404
    assert client.get("/api/storage/files/not-a-valid-id").status_code == 404


# --------------------------------------------------------------------------- existing book flows

def test_book_upload_download_restore_delete(env):
    from cps import ub
    admin = client_for(env, "s3test_admin")

    resp = admin.post("/upload", data={"btn-upload": (io.BytesIO(make_epub()), "s3-test.epub")},
                      content_type="multipart/form-data")
    assert resp.status_code == 200, resp.data[:500]
    book_id = int(re.search(r"/(\d+)$", resp.get_json()["location"]).group(1))
    try:
        # background TaskS3Sync mirrors the book file and its cover
        assert wait_for(lambda: stored("book_format", book_id)), "book was not mirrored to S3"
        record = stored("book_format", book_id)[0]
        assert record.variant == "EPUB" and record.object_key.startswith("books/{}/".format(book_id))
        assert record.object_key in s3_keys(env)
        assert record.size_bytes == len(make_epub())

        # plain downloads are redirected to a presigned S3 URL
        dl = admin.get("/download/{}/epub".format(book_id))
        assert dl.status_code == 302 and "X-Amz-Signature" in dl.headers["Location"]
        assert BUCKET in dl.headers["Location"]

        # uploading a cover through the existing edit form mirrors it as well
        from cps import calibre_db
        book = calibre_db.get_book(book_id)
        form = {"book_title": book.title, "author_name": "S3 Test Author", "series_index": "1",
                "description": "", "tags": "", "series": "", "publisher": "", "languages": "",
                "pubdate": "", "rating": "", "btn-upload-cover": (io.BytesIO(PNG), "cover.png")}
        resp = admin.post("/admin/book/{}".format(book_id), data=form, content_type="multipart/form-data")
        assert resp.status_code == 200
        assert wait_for(lambda: stored("book_cover", book_id)), "cover was not mirrored to S3"
        cover_key = stored("book_cover", book_id)[0].object_key
        assert cover_key.startswith("images/covers/{}/".format(book_id)) and cover_key in s3_keys(env)
        # title/author change moved the files on disk, S3 copy still downloads
        calibre_db.session.expire_all()
        book = calibre_db.get_book(book_id)
        assert "S3 Test Author" in book.path

        # author images uploaded through the existing admin route are mirrored and deleted
        author_id = book.authors[0].id
        resp = admin.post("/admin/upload_author_image",
                          data={"author_id": str(author_id), "image": (io.BytesIO(PNG), "face.png")})
        assert resp.status_code == 200 and "warning" not in resp.get_json(), resp.get_json()
        image_records = stored("author_image", author_id)
        assert len(image_records) == 1 and image_records[0].object_key in s3_keys(env)
        image_key = image_records[0].object_key
        fake = admin.post("/admin/upload_author_image",
                          data={"author_id": str(author_id), "image": (io.BytesIO(b"MZ" * 40), "face.png")})
        assert fake.status_code == 400
        assert admin.post("/admin/delete_author_image", json={"author_id": author_id}).status_code == 200
        assert stored("author_image", author_id) == [] and image_key not in s3_keys(env)

        # a lost local copy is restored from S3 for the reader
        local = os.path.join(env["library"], book.path, book.data[0].name + ".epub")
        original = open(local, "rb").read()
        os.unlink(local)
        shown = admin.get("/show/{}/epub".format(book_id))
        assert shown.status_code == 200 and shown.data == original
        assert os.path.isfile(local)

        # admin panel endpoints
        status = admin.get("/admin/aws-s3/storage-status").get_json()
        assert status["active"] is True and status["source"] == "environment"
        assert status["stored_files"]["book_format"]["count"] >= 1
        assert admin.post("/admin/aws-s3/sync", json={}).status_code == 202
        assert client_for(env, "s3test_uploader").post("/admin/aws-s3/sync", json={}).status_code == 403
    finally:
        keys = [r.object_key for r in stored("book_format", book_id) + stored("book_cover", book_id)]
        resp = admin.post("/delete/{}".format(book_id))
        assert resp.status_code == 302
    assert stored("book_format", book_id) == [] and stored("book_cover", book_id) == []
    assert not (set(keys) & s3_keys(env))
    ub.session.expire_all()


def test_admin_switch_controls_where_uploads_are_stored(env):
    from cps import ub, config
    from cps.models.settings import _Settings
    admin = client_for(env, "s3test_admin")
    row = ub.session.query(_Settings).first()
    saved = (row.aws_active, row.aws_enabled_at, row.aws_disabled_at)

    page = admin.get("/admin/aws-s3")
    assert page.status_code == 200 and b'id="aws-service-toggle"' in page.data
    assert client_for(env, "s3test_uploader").post("/admin/aws-s3/toggle", json={"enabled": False}).status_code == 403

    book_id = None
    try:
        resp = admin.post("/admin/aws-s3/toggle", json={"enabled": False})
        assert resp.status_code == 200 and resp.get_json()["aws_active"] is False
        ub.session.expire_all()
        assert ub.session.query(_Settings).first().aws_active is False   # persisted
        page = admin.get("/admin/aws-s3")
        assert b'id="aws-service-toggle" checked' not in page.data
        status = admin.get("/admin/aws-s3/storage-status").get_json()
        assert status["active"] is False and status["admin_enabled"] is False

        # switched off: the book stays in the local library folder only
        before = s3_keys(env)
        epub = make_epub()
        resp = admin.post("/upload", data={"btn-upload": (io.BytesIO(epub), "local-only.epub")},
                          content_type="multipart/form-data")
        assert resp.status_code == 200
        book_id = int(re.search(r"/(\d+)$", resp.get_json()["location"]).group(1))
        time.sleep(3)
        assert stored("book_format", book_id) == [] and s3_keys(env) == before
        dl = admin.get("/download/{}/epub".format(book_id))
        assert dl.status_code == 200 and dl.data == epub

        # switched on again: storage is active again
        resp = admin.post("/admin/aws-s3/toggle", json={"enabled": True})
        assert resp.status_code == 200 and resp.get_json()["aws_active"] is True
        assert admin.get("/admin/aws-s3/storage-status").get_json()["active"] is True
        assert b'id="aws-service-toggle" checked' in admin.get("/admin/aws-s3").data
    finally:
        if book_id is not None:
            admin.post("/delete/{}".format(book_id))
        row = ub.session.query(_Settings).first()
        row.aws_active, row.aws_enabled_at, row.aws_disabled_at = saved
        ub.session.commit()
        config.aws_active = saved[0] if saved[0] is not None else True


def test_book_delete_keeps_local_s3_and_database_consistent(env, monkeypatch):
    from cps import ub, calibre_db, config
    from cps.aws import s3Storage
    from cps.aws.s3Storage import StorageError
    from cps.models.forum import Thread
    admin = client_for(env, "s3test_admin")

    def thread_exists(book_id):
        with env["app"].app_context():
            return Thread.query.filter_by(book_id=book_id).first() is not None

    epub = make_epub()
    resp = admin.post("/upload", data={"btn-upload": (io.BytesIO(epub), "delete-test.epub")},
                      content_type="multipart/form-data")
    assert resp.status_code == 200
    book_id = int(re.search(r"/(\d+)$", resp.get_json()["location"]).group(1))
    try:
        # S3 copy and local library copy exist as soon as the upload request returns
        record = stored("book_format", book_id)[0]
        local = os.path.join(env["library"], record.local_path)
        assert os.path.isfile(local) and open(local, "rb").read() == epub
        assert env["s3"].get_object(Bucket=BUCKET, Key=record.object_key)["Body"].read() == epub
        epub_key = record.object_key

        # add a PDF format, then delete only that format: only its S3 object goes away
        book = calibre_db.get_book(book_id)
        form = {"book_title": book.title, "author_name": book.authors[0].name, "series_index": "1",
                "description": "", "tags": "", "series": "", "publisher": "", "languages": "",
                "pubdate": "", "rating": "", "btn-upload-format": (io.BytesIO(PDF), "extra.pdf")}
        assert admin.post("/admin/book/{}".format(book_id), data=form,
                          content_type="multipart/form-data").status_code == 200
        pdf_records = [r for r in stored("book_format", book_id) if r.variant == "PDF"]
        assert len(pdf_records) == 1 and pdf_records[0].object_key in s3_keys(env)
        pdf_key = pdf_records[0].object_key
        assert admin.post("/delete/{}/PDF".format(book_id)).status_code == 302
        assert pdf_key not in s3_keys(env) and epub_key in s3_keys(env)
        assert [r.variant for r in stored("book_format", book_id)] == ["EPUB"]
        assert thread_exists(book_id)                         # the book still exists

        # S3 refuses the deletion: nothing at all is deleted
        def denied(self, key):
            raise StorageError("Access denied by AWS while trying to delete '{}'".format(key), "access_denied", 503)
        monkeypatch.setattr(s3Storage.S3StorageService, "delete_object", denied)
        assert admin.post("/delete/{}".format(book_id)).status_code == 302
        calibre_db.session.expire_all()
        assert calibre_db.get_book(book_id) is not None and os.path.isfile(local)
        assert epub_key in s3_keys(env) and stored("book_format", book_id)
        assert thread_exists(book_id)
        monkeypatch.undo()

        # S3 switched off in the admin panel: the existing S3 objects are still removed
        config.aws_active = False
        assert admin.post("/delete/{}".format(book_id)).status_code == 302
        calibre_db.session.expire_all()
        assert calibre_db.get_book(book_id) is None
        assert not os.path.exists(os.path.dirname(local))
        assert epub_key not in s3_keys(env)
        assert stored("book_format", book_id) == [] and stored("book_cover", book_id) == []
        assert not thread_exists(book_id)
        book_id = None
    finally:
        config.aws_active = True
        monkeypatch.undo()
        if book_id is not None:
            admin.post("/delete/{}".format(book_id))
