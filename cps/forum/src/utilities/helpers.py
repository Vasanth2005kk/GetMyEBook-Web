from datetime import datetime
from cps.forum.database.models.category import Category
from cps.forum.src.cache import Cache

def now():
    return datetime.now()


def cached_categories():
    cache = Cache()
    categories = cache.get("categories")

    if categories is None:
        categories = list(
            map(lambda category: category.to_json(), Category.query.all())
        )

        cache.set("categories", categories, timeout=5*60)

    return categories


