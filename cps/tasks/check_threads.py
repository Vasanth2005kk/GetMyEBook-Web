# -*- coding: utf-8 -*-

from cps import logger, calibre_db, db, ub
from cps.services.worker import CalibreTask
from cps.forum.database.models import Thread, Category
from slugify import slugify
from flask_babel import lazy_gettext as N_

class TaskCheckThreads(CalibreTask):
    def __init__(self, task_message=N_('Check and create missing book threads')):
        super(TaskCheckThreads, self).__init__(task_message)
        self.log = logger.create()

    def run(self, worker_thread):
        self.log.info("Starting check for missing threads")
        
        try:
            # ensure forum models are loaded
            from cps.forum import db as forum_db
        except ImportError:
            self.log.error("Forum module not found, cannot check threads")
            self._handleError("Forum module missing")
            return

        # Get "General" category
        category = Category.query.filter_by(name="General").first()
        if not category:
            category = Category.query.first()
            
        if not category:
            self.log.error("No forum categories found")
            self._handleError("No categories found")
            return

        # Get Admin user
        admin_user = ub.session.query(ub.User).get(1)
        if not admin_user:
             admin_user = ub.session.query(ub.User).first()
             
        if not admin_user:
            self.log.error("No users found to assign threads to")
            return

        # Get all books
        try:
            books = calibre_db.session.query(db.Books).all()
        except Exception as e:
            self.log.error(f"Failed to query books: {e}")
            self._handleError(f"Database error: {e}")
            return

        created_count = 0
        skipped_count = 0
        total_books = len(books)
        
        for i, book in enumerate(books):
            if self.stat == 5: # STAT_CANCELLED
                return
            
            # Update progress
            self.progress = float(i) / total_books

            try:
                # Check if thread exists
                existing_thread = Thread.query.filter_by(title=book.title).first()
                if existing_thread:
                    skipped_count += 1
                    continue
                    
                content = f"Official discussion thread for **{book.title}**."
                if book.authors:
                    try:
                        author_names = [a.name for a in book.authors]
                        content += f" by {', '.join(author_names)}."
                    except:
                        pass

                thread = Thread(
                    title=book.title,
                    category_id=category.id,
                    content=content,
                    user_id=admin_user.id,
                    slug=slugify(book.title)[:240],
                    book_id=book.id,
                    views_count=0
                )
                thread.save()
                created_count += 1
                
            except Exception as e:
                self.log.error(f"Error creating thread for {book.title}: {e}")

        self.log.info(f"Thread check complete. Created: {created_count}, Skipped: {skipped_count}")
        self._handleSuccess()

    @property
    def name(self):
        return "Check Missing Threads"

    @property
    def is_cancellable(self):
        return True
