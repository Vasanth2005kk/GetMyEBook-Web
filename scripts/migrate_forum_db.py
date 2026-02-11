#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Forum Database Migration and Seeding Script
Creates forum tables and seeds initial data
"""
import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)

from cps import create_app
from cps.forum import db
from cps.forum.database.models.category import Category

def create_forum_tables():
    """Create all forum database tables"""
    app = create_app()
    with app.app_context():
        print("🔧 Creating forum database tables...")
        try:
            db.create_all()
            print("✅ Forum tables created successfully")
            return True
        except Exception as e:
            print(f"❌ Error creating tables: {e}")
            return False

def seed_categories():
    """Seed initial forum categories"""
    app = create_app()
    with app.app_context():
        print("🌱 Seeding initial forum categories...")
        
        categories = [
            {
                'name': 'General Discussion',
                'slug': 'general',
                'description': 'General discussions about books and reading'
            },
            {
                'name': 'Book Reviews',
                'slug': 'book-reviews',
                'description': 'Share your book reviews and ratings'
            },
            {
                'name': 'Book Recommendations',
                'slug': 'recommendations',
                'description': 'Ask for and share book recommendations'
            },
            {
                'name': 'Author Discussions',
                'slug': 'authors',
                'description': 'Discuss your favorite authors'
            },
            {
                'name': 'Technical Support',
                'slug': 'support',
                'description': 'Get help with the application'
            },
            {
                'name': 'Feature Requests',
                'slug': 'features',
                'description': 'Suggest new features'
            },
        ]
        
        created_count = 0
        skipped_count = 0
        
        for cat_data in categories:
            try:
                # Check if category already exists
                existing = Category.query.filter_by(slug=cat_data['slug']).first()
                
                if existing:
                    print(f"⏭️  Category '{cat_data['name']}' already exists, skipping")
                    skipped_count += 1
                    continue
                
                # Create new category
                category = Category(
                    name=cat_data['name'],
                    slug=cat_data['slug']
                )
                
                db.session.add(category)
                created_count += 1
                print(f"✅ Created category: {cat_data['name']}")
                
            except Exception as e:
                print(f"❌ Error creating category '{cat_data['name']}': {e}")
        
        try:
            db.session.commit()
            print(f"\n🎉 Seeding complete: {created_count} created, {skipped_count} skipped")
            return True
        except Exception as e:
            print(f"❌ Error committing categories: {e}")
            db.session.rollback()
            return False

def migrate_users():
    """Sync all Calibre users to forum"""
    from cps.forum.auth_bridge import bulk_sync_all_users
    
    app = create_app()
    with app.app_context():
        print("👥 Syncing Calibre users to forum...")
        success, errors = bulk_sync_all_users()
        
        if errors < 0:
            print("❌ User sync failed")
            return False
        else:
            print(f"✅ User sync complete: {success} users synced, {errors} errors")
            return True

def main():
    """Run all migration steps"""
    print("="*60)
    print("🚀 Forum Database Migration")
    print("="*60)
    print()
    
    # Create app only once
    print("Initializing application...")
    app = create_app()
    
    with app.app_context():
        # Step 1: Create tables (already done during app creation)
        print(f"\n{'='*60}")
        print("Step: Create Tables")
        print(f"{'='*60}")
        print("✅ Forum tables created during app initialization")
        
        # Step 2: Seed categories
        print(f"\n{'='*60}")
        print("Step: Seed Categories")
        print(f"{'='*60}")
        
        categories = [
            {'name': 'General Discussion', 'slug': 'general'},
            {'name': 'Book Reviews', 'slug': 'book-reviews'},
            {'name': 'Recommendations', 'slug': 'recommendations'},
            {'name': 'Authors', 'slug': 'authors'},
            {'name': 'Technical Support', 'slug': 'support'},
            {'name': 'Feature Requests', 'slug': 'features'},
        ]
        
        created_count = 0
        skipped_count = 0
        
        for cat_data in categories:
            try:
                existing = Category.query.filter_by(slug=cat_data['slug']).first()
                
                if existing:
                    print(f"⏭️  Category '{cat_data['name']}' already exists")
                    skipped_count += 1
                    continue
                
                category = Category(name=cat_data['name'], slug=cat_data['slug'])
                db.session.add(category)
                created_count += 1
                print(f"✅ Created category: {cat_data['name']}")
                
            except Exception as e:
                print(f"❌ Error creating category '{cat_data['name']}': {e}")
        
        try:
            db.session.commit()
            print(f"\n✅ Categories: {created_count} created, {skipped_count} skipped")
        except Exception as e:
            print(f"❌ Error committing categories: {e}")
            db.session.rollback()
        
        # Step 3: Sync users
        print(f"\n{'='*60}")
        print("Step: Sync Users")
        print(f"{'='*60}")
        
        from cps.forum.auth_bridge import bulk_sync_all_users
        success, errors = bulk_sync_all_users()
        
        if errors < 0:
            print("❌ User sync failed")
        else:
            print(f"✅ User sync complete: {success} users synced, {errors} errors")
    
    print("\n" + "="*60)
    print("🎉 Forum migration completed successfully!")
    print("="*60)
    print("\nYou can now:")
    print("  • Start your app: python cps.py")
    print("  • Access forum at: http://localhost:8083/forum")
    print("  • Existing users can login and access forum automatically")
    print()
    
    return True

if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n❌ Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
