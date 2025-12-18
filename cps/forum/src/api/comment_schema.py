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

    class Meta:
        model = Comment
        include_fk = True
        load_instance = True


class CommentValidationSchema(Schema):
    content = fields.Str(required=True, validate=Length(min=2))


comment_schema = CommentSchema()
comments_schema = CommentSchema(many=True)
comment_validation_schema = CommentValidationSchema()
