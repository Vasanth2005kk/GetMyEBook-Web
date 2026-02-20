import sys
import os
import logging
from slugify import slugify

# Add current directory to path so we can import cps
sys.path.append(os.getcwd())

from cps import create_app, calibre_db, ub, db
from cps.forum.database.models import Thread, Category
from cps.forum.database.seeds.category_seeder import categories_run

# Configure logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def create_threads():
    app = create_app()
    with app.app_context():
        # Auto-create default categories if they don't exist
        try:
            categories_run()
            log.info("Default categories checked/created successfully.")
        except Exception as e:
            log.warning(f"Could not auto-create categories: {e}")
        
        log.info("Starting thread creation for existing books...")
        
        # Get "General" category
        category = Category.query.filter_by(name="General").first()
        if not category:
            category = Category.query.first()
            
        if not category:
            log.error("Error: No forum categories found. Please create a category first.")
            return

        log.info(f"Using category: {category.name}")
        
        # Get all books
        books = calibre_db.session.query(db.Books).all()
        log.info(f"Found {len(books)} books.")
        
        created_count = 0
        skipped_count = 0
        
        # Get Admin user (try ID 1)
        admin_user = ub.session.query(ub.User).get(1)
        if not admin_user:
             log.warning("Warning: No admin user found (ID 1). Using first user found.")
             admin_user = ub.session.query(ub.User).first()
             
        if not admin_user:
            log.error("Error: No users found.")
            return

        # log.info(f"Assigning threads to user: {admin_user.name}")

        for book in books:
            # Check if thread exists
            existing_thread = Thread.query.filter_by(title=book.title).first()
            if existing_thread:
                skipped_count += 1
                continue
                
            content = f"Official discussion thread for **{book.title}**."
            try:
                # Authors
                if book.authors:
                    author_names = [a.name for a in book.authors]
                    content += f" by {', '.join(author_names)}."
            except Exception as e:
                log.warning(f"Could not get authors for book {book.title}: {e}")

            try:
                thread = Thread(
                    title=book.title,
                    category_id=category.id,
                    content=content,
                    user_id=admin_user.id,
                    slug=slugify(book.title)[:240], # Truncate strict for DB limit
                    views_count=0,
                    book_id = book.id   
                )
                thread.save()
                created_count += 1
                log.info(f"Created thread for: {book.title}")
            except Exception as e:
                log.error(f"Failed to create thread for {book.title}: {e}")

        log.info(f"Finished.")
        log.info(f"Created: {created_count}")
        log.info(f"Skipped: {skipped_count}")

if __name__ == "__main__":
    create_threads()
