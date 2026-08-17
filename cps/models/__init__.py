"""
cps/models/__init__.py
-----------------------
Top-level models package for GetMyEBook-Web.
Sub-packages:
  - cps.models.forum  — all SQLAlchemy models for the forum feature
"""
from cps.models.forum import (   # noqa: F401
  Base,
  Category,
  Thread,
  Comment,
  CommentLike,
  Emoji,
)

# Import all model modules so that importing `cps.models` registers
# every declarative model with `Base.metadata`. This ensures Alembic
# autogenerate sees all tables even when some model modules are only
# referenced from optional subsystems.
from . import ub
from . import db
from . import metadatadb
from . import settings

# Additional model modules that may not be imported during normal
# runtime startup but need to be registered for migrations.
from . import awstbl
from . import authors
from . import ratings
from . import tags
from . import comments
from . import identifiers
from . import libraryId

__all__ = [
    "Base",
    "Category",
    "Thread",
    "Comment",
    "CommentLike",
    "Emoji",
    "ub",
    "db",
    "metadatadb",
    "settings",
]
