from flask import Blueprint, jsonify, request, abort
from cps.forum import db
from flask_login import current_user, login_required
from cps.forum.database.models import Thread, Comment
from cps.forum.src.api.comment_schema import comments_schema, comment_schema
from cps.forum.src.utilities.helpers import now
from cps.forum.src.api.comment_schema import comment_validation_schema
from marshmallow import ValidationError


comments_blueprint = Blueprint("comments", __name__)


@login_required
@comments_blueprint.route('/threads/<int:thread_id>/comments', methods=["GET", "POST"])
def index(thread_id):
    thread = Thread.query.get_or_404(thread_id)

    if request.method == "POST":
        try:
            comment_validation_schema.load(request.json)
        except ValidationError as err:
            return jsonify(err.messages), 400

        comment = Comment(content=request.json["content"], user_id=current_user.id, thread_id=thread.id)
        comment.save()

        thread.increment("comments_count")

        return jsonify(comment_schema.dump(comment)), 201

    else:
        comments = Comment.query.filter_by(thread_id=thread.id)\
                                .order_by(Comment.created_at.desc())\
                                .all()
        return jsonify(comments_schema.dump(comments)), 200


@comments_blueprint.route('/comments/<int:comment_id>', methods=["GET", "PATCH", "DELETE"])
def show(comment_id):
    comment = Comment.query.get_or_404(comment_id)

    if not comment.is_owner(current_user):
        return jsonify({"message": "You are not authorized to perform this action"}), 403

    if request.method == "DELETE":
        comment.delete()
        return jsonify([]), 204

    if request.method == "PATCH":
        comment.update({
            "content": request.json["content"],
            "updated_at": now()
        })

        return jsonify(comment_schema.dump(comment)), 200

@comments_blueprint.route('/comments/<int:comment_id>/like', methods=["POST"])
@login_required
def like(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    
    # Check if already liked
    # We can use the dynamic relationship or query directly
    # Since we need to delete if exists, querying the association object is better
    from cps.forum.database.models.like import CommentLike
    
    existing_like = CommentLike.query.filter_by(user_id=current_user.id, comment_id=comment.id).first()
    
    if existing_like:
        existing_like.delete() # Base model has delete() method
        liked = False
    else:
        new_like = CommentLike(user_id=current_user.id, comment_id=comment.id)
        new_like.save() # Base model has save() method
        liked = True
        
    return jsonify({
        "likes_count": comment.likes_count, 
        "liked_by_current_user": liked
    }), 200
