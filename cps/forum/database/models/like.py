from cps.forum.database.models import Base
from cps.forum import db

class CommentLike(Base):
    __tablename__ = "forum_comment_likes"
    
    user_id = db.Column(db.Integer, nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey("forum_comments.id"), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'comment_id', name='unique_user_comment_like'),
    )
