from cps.forum import ma
from marshmallow import Schema, fields
from marshmallow.validate import Length
from .thread_schema import ThreadSchema
from .user_schema import UserSchema
from cps.forum.database.models.comment import Comment


class CommentSchema(ma.SQLAlchemyAutoSchema):
    thread = ma.Nested(ThreadSchema)
    owner = ma.Nested(UserSchema)
    likes_count = fields.Integer(dump_only=True)
    liked_by_current_user = fields.Boolean(dump_only=True)
    current_user_reaction = fields.String(dump_only=True)
    top_reaction = fields.String(dump_only=True)
    
    # Self-referential nested field for replies
    replies = fields.Nested("CommentSchema", many=True, dump_only=True)
    parent_id = fields.Integer(allow_none=True)

    class Meta:
        model = Comment
        include_fk = True
        load_instance = True


class CommentValidationSchema(Schema):
    content = fields.Str(required=True, validate=Length(min=2))
    parent_id = fields.Integer(required=False, allow_none=True)


comment_schema = CommentSchema()
comments_schema = CommentSchema(many=True)
comment_validation_schema = CommentValidationSchema()
