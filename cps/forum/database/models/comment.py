from cps.forum.database.models import Base
from cps.forum import db


class Comment(Base):
    __tablename__ = "forum_comments"

    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer)  # Changed from forum_users to users (Foreign key constraint removed to avoid metadata mismatch)
    thread_id = db.Column(db.Integer, db.ForeignKey("forum_threads.id"))
    
    # Self-referential relationship for nested replies
    parent_id = db.Column(db.Integer, db.ForeignKey("forum_comments.id"), nullable=True)
    
    # Relationship within forum database
    thread = db.relationship("Thread", back_populates="comments")
    likes = db.relationship("CommentLike", backref="comment", cascade="all, delete-orphan", lazy='dynamic')
    
    # Self-referential relationship for replies
    replies = db.relationship(
        "Comment",
        backref=db.backref("parent", remote_side="Comment.id"),
        cascade="all, delete-orphan",
        lazy="select",  # Lazy load to ensure deep nesting works (Marshmallow triggers loading)
        order_by="Comment.created_at"
    )

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
    def current_user_reaction(self):
        from flask_login import current_user
        if not current_user.is_authenticated:
            return None
        like = self.likes.filter_by(user_id=current_user.id).first()
        return like.reaction_type if like else None

    @property
    def top_reaction(self):
        """Returns the most common reaction type for this comment"""
        from sqlalchemy import func
        from .like import CommentLike
        # This relies on the dynamic loader
        if self.likes_count == 0:
            return None
        
        # Get reaction with highest count
        try:
            top = self.likes.with_entities(CommentLike.reaction_type, func.count(CommentLike.reaction_type).label('cnt'))\
                .group_by(CommentLike.reaction_type)\
                .order_by(func.count(CommentLike.reaction_type).desc())\
                .first()
            return top.reaction_type if top else None
        except Exception:
            return 'like' # Fallback

    @property
    def owner(self):
        """Load user from main users table"""
        if not self.user_id:
            return None
        from cps import ub
        return ub.session.query(ub.User).filter(ub.User.id == self.user_id).first()

    def is_owner(self, user):
        return user and user.id == self.user_id

    @property
    def is_reply(self):
        """Check if this comment is a reply to another comment"""
        return self.parent_id is not None

    @property
    def replies_count(self):
        """Get the count of direct replies to this comment"""
        return len(self.replies) if self.replies else 0

    def get_all_replies(self):
        """Get all replies (recursively) to this comment"""
        all_replies = []
        for reply in self.replies:
            all_replies.append(reply)
            all_replies.extend(reply.get_all_replies())
        return all_replies
