from cps.forum.database.models.category import Category
from flask_seeder import Seeder
from slugify import slugify
import logging

log = logging.getLogger(__name__)

category_names = ["General", "Book Discussion", "Recommendations", "Technical Support"]


class CategorySeeder(Seeder):
    def run(self):
        for category_name in category_names:
            # Check if category already exists
            existing = Category.query.filter_by(name=category_name).first()
            if existing:
                log.info(f"Category '{category_name}' already exists, skipping.")
                continue
            
            try:
                category = Category(name=category_name, slug=slugify(category_name))
                category.save()
                log.info(f"Created category: {category_name}")
            except Exception as e:
                log.error(f"Failed to create category '{category_name}': {e}")

def categories_run():
    # Only run if no categories exist to avoid duplication
    if Category.query.first() is None:
        log.info("No categories found. Creating default categories...")
        run = CategorySeeder()
        run.run()
    else:
        log.info("Categories already exist. Skipping category creation.")