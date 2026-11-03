# -*- coding: utf-8 -*-

from flask_babel import lazy_gettext as N_

from cps import db, logger, ub
from cps.services.worker import CalibreTask
from cps.aws.s3Storage import StorageError, get_storage
from cps.aws import storageSync
from cps.models.storedfile import StoredFile

log = logger.create()


class TaskS3Sync(CalibreTask):
    """
    Mirror book files and covers from the local library to S3.

    book_ids=None mirrors the whole library and removes S3 objects of books
    that no longer exist. `formats` limits a run to the given formats
    (an empty list means none, e.g. a cover-only sync); force=True re-uploads
    even if an up-to-date copy is already recorded.
    """

    def __init__(self, task_message, book_ids=None, formats=None, include_cover=True, force=False, user_id=None):
        super(TaskS3Sync, self).__init__(task_message)
        self.book_ids = list(book_ids) if book_ids is not None else None
        self.formats = [f.upper() for f in formats] if formats is not None else None
        self.include_cover = include_cover
        self.force = force
        self.user_id = user_id
        self.synced = 0

    def run(self, worker_thread):
        storage = get_storage()
        if storage is None:
            self._handleError(N_("AWS S3 storage is not configured"))
            return
        local_db = db.CalibreDB(expire_on_commit=False, init=True)
        errors = []
        try:
            query = local_db.session.query(db.Books)
            if self.book_ids is not None:
                query = query.filter(db.Books.id.in_(self.book_ids))
            books = query.all()
            for index, book in enumerate(books):
                errors.extend(self._sync_book(storage, book))
                errors.extend(self._remove_if_deleted(local_db, storage, book.id))
                self.progress = (index + 1) / (len(books) + (1 if self.book_ids is None else 0))
            if self.book_ids is None:
                errors.extend(self._remove_orphans(storage, {str(b.id) for b in books}))
        except Exception as e:
            log.error_or_exception(e)
            errors.append(str(e))
        finally:
            local_db.session.close()
            ub.session.remove()

        if errors:
            log.error("S3 sync finished with %d error(s): %s", len(errors), "; ".join(errors[:5]))
            self._handleError(N_("S3 sync failed for %(count)s file(s): %(error)s",
                                 count=len(errors), error=errors[0]))
        else:
            log.info("S3 sync finished, %d file(s) in S3", self.synced)
            self._handleSuccess()

    def _sync_book(self, storage, book):
        errors = []
        for data in book.data:
            if self.formats is not None and data.format.upper() not in self.formats:
                continue
            errors.extend(self._run_one(lambda: storageSync.mirror_book_format(
                book, data, user_id=self.user_id, force=self.force, storage=storage)))
        if self.include_cover and book.has_cover:
            errors.extend(self._run_one(lambda: storageSync.mirror_book_cover(
                book, user_id=self.user_id, force=self.force, storage=storage)))
        # records created before local paths were tracked get theirs filled in
        storageSync.refresh_local_paths(book)
        return errors

    def _run_one(self, storage_call):
        try:
            if storage_call() is not None:
                self.synced += 1
            return []
        except StorageError as e:
            return [e.message]

    @staticmethod
    def _remove_if_deleted(local_db, storage, book_id):
        """The book may have been deleted while it was being uploaded: drop what was just stored."""
        local_db.session.expire_all()
        if local_db.session.query(db.Books.id).filter(db.Books.id == book_id).first():
            return []
        records = storageSync.book_storage_records(book_id)
        if records:
            log.info("Book %s was deleted during S3 sync, removing %d uploaded object(s)", book_id, len(records))
        return storageSync.delete_records(storage, records)

    @staticmethod
    def _remove_orphans(storage, existing_ids):
        query = ub.session.query(StoredFile) \
            .filter(StoredFile.entity_type.in_([storageSync.BOOK_FORMAT, storageSync.BOOK_COVER]))
        if existing_ids:
            query = query.filter(StoredFile.entity_id.notin_(existing_ids))
        orphans = query.all()
        if orphans:
            log.info("Removing %d S3 object(s) of deleted books", len(orphans))
        return storageSync.delete_records(storage, orphans)

    @property
    def name(self):
        return N_("Sync to S3")

    def __str__(self):
        return "Sync to S3"

    @property
    def is_cancellable(self):
        return False

