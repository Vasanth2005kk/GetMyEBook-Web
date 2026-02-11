#!/usr/bin/env python3
"""
Add book_id column to forum_threads table
This script works directly with the database connection
"""

import sys
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
# env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv("/home/vasanth/Desktop/GetMyEBook-Web/.env")

def add_book_id_column():
    """Add book_id column to forum_threads table if it doesn't exist"""
    
    try:
        # Get database config from environment variables (same as in cps/__init__.py)
        database_url = os.getenv('DATABASE_URL')
        
        if not database_url:
            db_user = os.getenv('DB_USERNAME')
            db_password = os.getenv('DB_PASSWORD')
            db_host = os.getenv('DB_HOST', 'localhost')
            db_port = os.getenv('DB_PORT', '5432')
            db_name = os.getenv('DATABASENAME_APP')
            
            if not all([db_name, db_user, db_password]):
                print("✗ Error: Missing required database environment variables")
                print("  Please ensure DB_USERNAME, DB_PASSWORD, and DATABASENAME_APP are set in .env")
                return False
            
            # Properly encode the password for URL
            import urllib.parse
            encoded_password = urllib.parse.quote_plus(db_password)
            
            database_url = f"postgresql+psycopg2://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}"
        
        print(f"Connecting to database...")
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            print("Checking if book_id column exists...")
            
            # Check if column exists
            check_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'forum_threads' 
                AND column_name = 'book_id'
            """)
            
            result = conn.execute(check_query)
            exists = result.fetchone() is not None
            
            if exists:
                print("✓ book_id column already exists!")
                return True
            
            print("Adding book_id column to forum_threads table...")
            
            # Add the column
            add_column_query = text("""
                ALTER TABLE forum_threads 
                ADD COLUMN book_id INTEGER
            """)
            
            conn.execute(add_column_query)
            conn.commit()
            
            print("✓ Successfully added book_id column!")
            
            # Optional: Add index for better performance
            print("Adding index on book_id column...")
            index_query = text("""
                CREATE INDEX IF NOT EXISTS idx_forum_threads_book_id 
                ON forum_threads(book_id)
            """)
            
            conn.execute(index_query)
            conn.commit()
            
            print("✓ Successfully added index!")
            
            # Verify the column was added
            verify_query = text("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'forum_threads' 
                ORDER BY ordinal_position
            """)
            
            result = conn.execute(verify_query)
            columns = result.fetchall()
            
            print("\nCurrent forum_threads table structure:")
            print("-" * 60)
            for col in columns:
                print(f"  {col[0]:<20} {col[1]:<15} {'NULL' if col[2] == 'YES' else 'NOT NULL'}")
            print("-" * 60)
            
            return True
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Forum Thread Book Integration - Database Migration")
    print("=" * 60)
    print()
    
    success = add_book_id_column()
    
    print()
    if success:
        print("✓ Migration completed successfully!")
        print("\nYou can now restart your application.")
        sys.exit(0)
    else:
        print("✗ Migration failed!")
        print("\nPlease check the error messages above.")
        sys.exit(1)
