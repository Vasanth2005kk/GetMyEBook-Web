from cps.forum.database.models.category import Category
from flask_seeder import Seeder
from slugify import slugify



category_names = ["General", "Book Discussion", "Recommendations", "Technical Support"]


class CategorySeeder(Seeder):
    def run(self):
        for category_name in category_names:
            category = Category(name=category_name, slug=slugify(category_name))
            category.save()

def categories_run():
    # Only run if no categories exist to avoid duplication
    if Category.query.first() is None:
        run = CategorySeeder()
        run.run()