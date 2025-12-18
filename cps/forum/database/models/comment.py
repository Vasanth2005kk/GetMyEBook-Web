from cps.forum.database.models import Base
from cps.forum import db


class Comment(Base):
    __tablename__ = "forum_comments"

    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer)  # Changed from forum_users to users (Foreign key constraint removed to avoid metadata mismatch)
    thread_id = db.Column(db.Integer, db.ForeignKey("forum_threads.id"))
    
    # Relationship within forum database
    thread = db.relationship("Thread", back_populates="comments")
    likes = db.relationship("CommentLike", backref="comment", cascade="all, delete-orphan", lazy='dynamic')

    @property
    def likes_count(self):
        return self.likes.count()

    @property
    def liked_by_current_user(self):
        from flask_login import current_user
        if not current_user.is_authenticated:
            return False
        return self.likes.filter_by(user_id=current_user.id).first() is not None

    @property
    def owner(self):
        """Load user from main users table"""
        if not self.user_id:
            return None
        from cps import ub
        return ub.session.query(ub.User).filter(ub.User.id == self.user_id).first()

    def is_owner(self, user):
        return user and user.id == self.user_id
