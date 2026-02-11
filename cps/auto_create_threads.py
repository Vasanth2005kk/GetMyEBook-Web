import sys
import os
from . import logger
from slugify import slugify

# Add current directory to path so we can import cps
sys.path.append(os.getcwd())
# from cps import create_app , calibre_db , ub , db
log = logger.create()


def create_threads():
    from cps import calibre_db, ub, db
    from flask import has_app_context, current_app
    
    # Check if we're already in an app context
    if has_app_context():
        # Use the existing app context
        log.info("Using existing Flask app context for thread creation")
        _create_threads_logic(calibre_db, ub, db)
    else:
        # Create a new app context (for standalone execution)
        from cps import create_app
        log.info("Creating new Flask app context for thread creation")
        app = create_app()
        with app.app_context():
            _create_threads_logic(calibre_db, ub, db)


def _create_threads_logic(calibre_db, ub, db):
    """Internal function containing the actual thread creation logic"""
    from cps.forum.database.models import Thread, Category
    from .forum.database.seeds.category_seeder import categories_run
    
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
    session = calibre_db.session
    local_session = False
    temp_engine = None
    
    if session is None:
        from sqlalchemy.orm import scoped_session, sessionmaker
        
        target_engine = db.CalibreDB.engine
        
        if not target_engine:
            log.info("CalibreDB global engine not initialized. Creating temporary engine from Env Vars...")
            try:
                from sqlalchemy import create_engine
                from dotenv import load_dotenv
                import urllib.parse
                
                # Load env vars
                env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
                load_dotenv(env_path)
                
                db_user = os.getenv("DB_USERNAME")
                db_password = os.getenv("DB_PASSWORD")
                db_host = os.getenv("DB_HOST")
                db_port = os.getenv("DB_PORT")
                db_name = os.getenv("DATABASENAME_APP")
                
                if all([db_user, db_password, db_host, db_port, db_name]):
                    encoded_password = urllib.parse.quote_plus(db_password)
                    db_url = f"postgresql+psycopg2://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}"
                    temp_engine = create_engine(db_url, echo=False)
                    target_engine = temp_engine
                else:
                    log.error("Missing DB env vars. Cannot create temporary engine.")
            except Exception as e:
                log.error(f"Failed to create temporary engine: {e}")

        if target_engine:
            log.info("Creating temporary session from engine...")
            session_factory = sessionmaker(bind=target_engine)
            session = scoped_session(session_factory)
            local_session = True
        else:
             log.error("Error: CalibreDB engine not initialized and could not create temporary one. Cannot create threads.")
             return

    try:
        books = session.query(db.Books).all()
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
            if local_session:
                session.remove()
            return
    
        log.info(f"Assigning threads to user: {admin_user.name}")
    
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
                
    finally:
        if local_session:
             log.info("Closing temporary session.")
             session.remove()
        if temp_engine:
             log.info("Disposing temporary engine.")
             temp_engine.dispose()

    log.info(f"Finished.")
    log.info(f"Created: {created_count}")
    log.info(f"Skipped: {skipped_count}")

if __name__ == "__main__":
    create_threads()
