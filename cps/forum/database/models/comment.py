from cps.forum.database.models import Base
from cps.forum import db


class Comment(Base):
    __tablename__ = "forum_comments"

    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))  # Changed from forum_users to users
    thread_id = db.Column(db.Integer, db.ForeignKey("forum_threads.id"))
    
    # Relationship within forum database
    thread = db.relationship("Thread", back_populates="comments")

    @property
    def owner(self):
        """Load user from main users table"""
        if not self.user_id:
            return None
        from cps import ub
        return ub.session.query(ub.User).filter(ub.User.id == self.user_id).first()

    def is_owner(self, user):
        return user and user.id == self.user_id
