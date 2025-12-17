from cps.forum import db
from cps.forum.database.models import Base


class Category(Base):
    __tablename__ = "forum_categories"
    
    name = db.Column(db.String(100))
    slug = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=db.func.now())

    threads = db.relationship("Thread", back_populates="category")

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "created_at": self.created_at
        }


