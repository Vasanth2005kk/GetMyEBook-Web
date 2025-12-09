"""
Database Migration: Add Forum Columns to Users Table
This script adds forum-related columns to the main users table and
migrates data from forum_users table if it exists.
"""
import os
import sys
from sqlalchemy import create_engine, text, Column, String, DateTime, inspect
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cps.utils import get_env_path

# Load environment variables
load_dotenv(get_env_path())

DB_USER = os.getenv("DB_USERNAME")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DATABASENAME_APP")

def get_db_connection():
    """Create database connection"""
    from urllib.parse import quote
    encoded_password = quote(DB_PASSWORD)
    DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{encoded_password}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    engine = create_engine(DATABASE_URL, echo=True)
    Session = sessionmaker(bind=engine)
    return engine, Session()

def check_column_exists(engine, table_name, column_name):
    """Check if a column exists in a table"""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def check_table_exists(engine, table_name):
    """Check if a table exists"""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()

def migrate_forum_columns():
    """Add forum columns to users table and migrate data"""
    print("=" * 60)
    print("Forum Column Migration Script")
    print("=" * 60)
    
    engine, session = get_db_connection()
    
    try:
        # Check if users table exists
        if not check_table_exists(engine, 'users'):
            print("❌ Error: users table does not exist!")
            return False
        
        print("\n✓ Users table found")
        
        # Add forum_avatar column if it doesn't exist
        if not check_column_exists(engine, 'users', 'forum_avatar'):
            print("\n📝 Adding forum_avatar column...")
            session.execute(text("""
                ALTER TABLE users 
                ADD COLUMN forum_avatar VARCHAR(150) DEFAULT 'avatar.png'
            """))
            session.commit()
            print("✅ Added forum_avatar column")
        else:
            print("\n✓ forum_avatar column already exists")
        
        # Add forum_email_verified_at column if it doesn't exist
        if not check_column_exists(engine, 'users', 'forum_email_verified_at'):
            print("\n📝 Adding forum_email_verified_at column...")
            session.execute(text("""
                ALTER TABLE users 
                ADD COLUMN forum_email_verified_at TIMESTAMP NULL
            """))
            session.commit()
            print("✅ Added forum_email_verified_at column")
        else:
            print("\n✓ forum_email_verified_at column already exists")
        
        # Check if forum_users table exists and migrate data
        if check_table_exists(engine, 'forum_users'):
            print("\n📦 Found forum_users table - migrating data...")
            
            # Migrate avatar and email verification data
            result = session.execute(text("""
                UPDATE users u
                SET 
                    forum_avatar = COALESCE(fu.avatar, 'avatar.png'),
                    forum_email_verified_at = fu.email_verified_at
                FROM forum_users fu
                WHERE u.email = fu.email
                AND fu.avatar IS NOT NULL
            """))
            session.commit()
            
            rows_updated = result.rowcount
            print(f"✅ Migrated data for {rows_updated} users")
            
            # Ask user if they want to drop forum_users table
            print("\n⚠️  The forum_users table is no longer needed.")
            print("   It's recommended to drop it, but you may want to keep a backup first.")
            response = input("   Drop forum_users table? (yes/no): ").strip().lower()
            
            if response == 'yes':
                session.execute(text("DROP TABLE forum_users CASCADE"))
                session.commit()
                print("✅ Dropped forum_users table")
            else:
                print("ℹ️  Kept forum_users table (you can drop it manually later)")
        else:
            print("\n✓ No forum_users table found (clean installation)")
        
        # Update forum_threads foreign key if needed
        if check_table_exists(engine, 'forum_threads'):
            print("\n📝 Updating forum_threads foreign key...")
            
            # Check current foreign key
            inspector = inspect(engine)
            fks = inspector.get_foreign_keys('forum_threads')
            
            needs_update = False
            for fk in fks:
                if fk['constrained_columns'] == ['user_id'] and fk['referred_table'] == 'forum_users':
                    needs_update = True
                    fk_name = fk['name']
                    break
            
            if needs_update:
                print(f"   Dropping old foreign key: {fk_name}")
                session.execute(text(f"ALTER TABLE forum_threads DROP CONSTRAINT {fk_name}"))
                
                print("   Adding new foreign key to users table")
                session.execute(text("""
                    ALTER TABLE forum_threads 
                    ADD CONSTRAINT forum_threads_user_id_fkey 
                    FOREIGN KEY (user_id) REFERENCES users(id)
                """))
                session.commit()
                print("✅ Updated forum_threads foreign key")
            else:
                print("✓ forum_threads foreign key already correct")
        
        # Update forum_comments foreign key if needed
        if check_table_exists(engine, 'forum_comments'):
            print("\n📝 Updating forum_comments foreign key...")
            
            inspector = inspect(engine)
            fks = inspector.get_foreign_keys('forum_comments')
            
            needs_update = False
            for fk in fks:
                if fk['constrained_columns'] == ['user_id'] and fk['referred_table'] == 'forum_users':
                    needs_update = True
                    fk_name = fk['name']
                    break
            
            if needs_update:
                print(f"   Dropping old foreign key: {fk_name}")
                session.execute(text(f"ALTER TABLE forum_comments DROP CONSTRAINT {fk_name}"))
                
                print("   Adding new foreign key to users table")
                session.execute(text("""
                    ALTER TABLE forum_comments 
                    ADD CONSTRAINT forum_comments_user_id_fkey 
                    FOREIGN KEY (user_id) REFERENCES users(id)
                """))
                session.commit()
                print("✅ Updated forum_comments foreign key")
            else:
                print("✓ forum_comments foreign key already correct")
        
        print("\n" + "=" * 60)
        print("✅ Migration completed successfully!")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n❌ Error during migration: {e}")
        session.rollback()
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()

if __name__ == "__main__":
    success = migrate_forum_columns()
    sys.exit(0 if success else 1)
