from sqlalchemy.ext.hybrid import hybrid_property

from cps.forum import db
from . import Base
from .comment import Comment


class Thread(Base):

    json_attributes = ("id", "title", "slug", "content", "user_id", "category_id", "comments_count", "book_id")

    __tablename__ = "forum_threads"
    title = db.Column(db.String(250), nullable=False)
    slug = db.Column(db.String(250), nullable=False)
    content = db.Column(db.Text)
    user_id = db.Column(db.Integer)  # Changed from forum_users to users (Foreign key constraint removed to avoid metadata mismatch)
    category_id = db.Column(db.Integer, db.ForeignKey("forum_categories.id"))
    book_id = db.Column(db.Integer, nullable=False,unique=True)  # Link to book in calibre database
    views_count = db.Column(db.Integer, nullable=False, default=0)
    comments_count = db.Column(db.Integer, default=0)
    best_comment_id = db.Column(db.Integer, nullable=True)

    # Relationships within forum database
    category = db.relationship("Category", back_populates="threads")
    comments = db.relationship("Comment", back_populates="thread")

    @property
    def owner(self):
        """Load user from main users table"""
        if not self.user_id:
            return None
        from cps import ub
        return ub.session.query(ub.User).filter(ub.User.id == self.user_id).first()

    @property
    def summary(self):
        return self.content[0:300] + "..."

    def is_owner(self, user):
        return user and user.id == self.user_id

    def add_comment(self, content, owner):
        comment = Comment(content=content, user_id=owner.id, thread_id=self.id)
        comment.save()

        return comment
    @staticmethod 
    def thread_rollback():
        db.session.rollback()

    @hybrid_property
    def has_comments(self):
        return self.comments_count > 0

