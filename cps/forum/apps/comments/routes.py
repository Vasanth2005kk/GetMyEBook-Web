from flask import Blueprint, jsonify, request, abort
from cps.forum import db
from flask_login import current_user, login_required
from cps.forum.database.models import Thread, Comment
from cps.forum.src.api.comment_schema import comments_schema, comment_schema
from cps.forum.src.utilities.helpers import now
from cps.forum.src.api.comment_schema import comment_validation_schema
from marshmallow import ValidationError

comments_blueprint = Blueprint("comments", __name__)


@comments_blueprint.route('/threads/<int:thread_id>/comments', methods=["GET", "POST"])
def index(thread_id):
    thread = Thread.query.get_or_404(thread_id)

    if request.method == "POST":
        if not current_user.is_authenticated:
            return abort(401)

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
    if request.method == "GET":
        return jsonify(comment_schema.dump(comment)), 200

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
    
    from cps.forum.database.models.like import CommentLike
    
    data = request.get_json(silent=True) or {}
    
    # Check for explicit reaction type in payload
    # Frontend might send: reaction_type, type, or reaction
    # Value can be a string ('love') or None (explicit unlike)
    has_payload = False
    reaction_val = None
    
    for key in ['reaction_type', 'type', 'reaction']:
        if key in data:
            has_payload = True
            reaction_val = data[key]
            break
            
    existing_like = CommentLike.query.filter_by(user_id=current_user.id, comment_id=comment.id).first()
    
    if has_payload:
        if reaction_val:
            # Upsert (Create or Update)
            if existing_like:
                existing_like.reaction_type = reaction_val
                existing_like.save()
            else:
                new_like = CommentLike(user_id=current_user.id, comment_id=comment.id, reaction_type=reaction_val)
                new_like.save()
            liked = True
            current_type = reaction_val
        else:
            # Explicit unlike (null sent)
            if existing_like:
                existing_like.delete()
            liked = False
            current_type = None
    else:
        # Legacy Toggle (No payload)
        if existing_like:
            existing_like.delete()
            liked = False
            current_type = None
        else:
            # Default to 'like'
            new_like = CommentLike(user_id=current_user.id, comment_id=comment.id, reaction_type='like')
            new_like.save()
            liked = True
            current_type = 'like'
        
    return jsonify({
        "likes_count": comment.likes_count, 
        "liked_by_current_user": liked,
        "current_user_reaction": current_type
    }), 200
