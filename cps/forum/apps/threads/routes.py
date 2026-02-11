from flask import redirect, url_for, flash, Blueprint, render_template, abort, request , jsonify
from flask_login import login_required, current_user
from slugify import slugify
from .forms import ThreadCreationForm
from cps.forum.database.models import Thread, Category , Emoji
from cps.forum.src.decorators.email_verified import email_verified
from sqlalchemy.orm import joinedload
import requests
from cps.logger import create
from sqlalchemy.exc import IntegrityError

thread_blueprint = Blueprint("threads", __name__, template_folder="templates")

log = create()


@thread_blueprint.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if not current_user.role_admin():
        flash("Only administrators can create new threads.", "error")
        return redirect(url_for("main.index"))

    thread_form = ThreadCreationForm()

    # Pre-fill from query args or form
    book_id = request.args.get('book_id', type=int) or request.form.get('book_id', type=int)

    if request.method == 'GET':
        title_arg = request.args.get('title')
        if title_arg and not thread_form.title.data:
            thread_form.title.data = title_arg
            thread_form.content.data = request.args.get('book_description', 'formal discussion thread for **' + title_arg + '**.')

    try:
        if thread_form.validate_on_submit():
            title = thread_form.title.data
            category_id = thread_form.category_id.data
            content = thread_form.content.data
            user_id = current_user.id

            thread = Thread(title=title,
                            category_id=category_id,
                            content=content,
                            user_id=user_id,
                            slug=slugify(title),
                            views_count=0,
                            book_id=book_id
                            )
            thread.save()

            flash("Your question has been posted successfully", "success")
            return redirect(url_for("main.index"))
    except IntegrityError :
        Thread.thread_rollback()
        flash("A thread for this book already exists. Please edit the existing thread.", "error")
    return render_template("threads/create.html", form=thread_form, book_id=book_id)


@thread_blueprint.route("/book/<int:book_id>")
@login_required
def book_thread(book_id):
    from cps import calibre_db
    book = calibre_db.get_book(book_id)
    if not book:
        abort(404)
    
    # Find thread by book_id (more reliable than title matching)
    thread = Thread.query.filter_by(book_id=book_id).first()
    
    if thread:
        return redirect(url_for('threads.show', 
                              category_slug=thread.category.slug, 
                              thread_slug=thread.slug))
    
    # If no thread found
    if current_user.role_admin():
        book_description = ""
        if book.comments and len(book.comments) > 0:
            # Extract the text from the first comment object
            book_description = book.comments[0].text
        else:
            book_description = f"Official discussion thread for **{book.title}**."

        flash(f"No discussion thread found for '{book.title}'. You can create one now.", "info")
        return redirect(url_for('threads.create', title=book.title, book_id=book_id, book_description=book_description))
    else:
        flash(f"No discussion thread has been created for '{book.title}' yet.", "info")
        # Go to forum index or search?
        # Search might show partial matches
        # Assuming main.index is the forum home
        return redirect(url_for('main.index'))


@thread_blueprint.route("<string:category_slug>")
def category_threads(category_slug):
    category = Category.query.filter_by(slug=category_slug).first_or_404()

    page = request.args.get('page', 1, type=int)

    threads = Thread.query\
                    .filter_by(category_id=category.id)\
                    .order_by(Thread.created_at.desc())\
                    .options(joinedload(Thread.category))\
                    .options(joinedload(Thread.comments))\
                    .paginate(page=page, per_page=10, error_out=False)

    return render_template('main/index.html', threads=threads)



@thread_blueprint.route("<string:category_slug>/<string:thread_slug>", methods=["GET", "POST", "DELETE", "PUT"])
def show(category_slug, thread_slug):
    from cps import calibre_db
    from sqlalchemy import func, desc
    
    category = Category.query.filter_by(slug=category_slug).first_or_404()
    thread = Thread.query\
        .filter_by(category_id=category.id, slug=thread_slug)\
        .first_or_404()

    if request.method == "GET":
        thread.update({"views_count": thread.views_count + 1})

    # Support for method overriding via _method query arg or form field
    method = request.args.get('_method', request.method).upper()
    if method == "DELETE":
        if thread.is_owner(current_user):
            thread.delete()
            flash("Your question has been deleted successfully", "success")

            return redirect(url_for('main.index'))
        else:
            abort(403)
        
    if method == "PUT":
        if thread.is_owner(current_user):
            thread.update({
                "title": request.form['title'],
                "slug": slugify(request.form['title']),
                "category_id": request.form['category_id'],
                "content": request.form['content']
            })

            flash("Your question has been updated successfully", "success")

            return redirect(url_for('threads.show', category_slug=thread.category.slug, thread_slug=thread.slug))
        else:
            abort(403)
    
    # Fetch book data if this thread is linked to a book
    book = None
    book_format = None
    log.info(f"thread All datas :")
    log.info({
    c.name: getattr(thread, c.name)
    for c in thread.__table__.columns
    })
    if thread.book_id:
        book = calibre_db.get_book(thread.book_id)
        if book:
            # Get available formats for the book
            for format_obj in book.data:
                if format_obj.format.lower() in ['epub', 'pdf', 'txt']:
                    book_format = format_obj.format.lower()
                    break
    
    # Get top contributors (users with most comments)
    from cps.forum.database.models import Comment
    from cps.forum import db
    from cps import ub
    top_contributors_data = db.session.query(
        Comment.user_id, 
        func.count(Comment.id).label('comment_count')
    ).group_by(Comment.user_id)\
     .order_by(desc('comment_count'))\
     .limit(5).all()
    
    top_contributors = []
    for user_id, comment_count in top_contributors_data:
        user = ub.session.query(ub.User).filter(ub.User.id == user_id).first()
        if user:
            top_contributors.append({
                'user': user,
                'comment_count': comment_count
            })
    
    # Get recent discussions (recent threads)
    recent_discussions = Thread.query\
        .order_by(Thread.updated_at.desc())\
        .limit(5).all()

    log.info(f"show.html chacking parms {book},{book_format} thread {thread}")
    return render_template("threads/show.html",
                        thread=thread, 
                        book=book,
                        book_format=book_format,
                        top_contributors=top_contributors,
                        recent_discussions=recent_discussions)


@thread_blueprint.route("<string:category_slug>/<string:thread_slug>/edit")
@login_required
def edit(category_slug, thread_slug):

    category = Category.query.filter_by(slug=category_slug).first_or_404()
    thread = Thread.query.filter_by(category_id=category.id, slug=thread_slug).first_or_404()

    if not thread.is_owner(current_user):
        abort(403)

    thread_form = ThreadCreationForm()

    thread_form.title.data = thread.title
    thread_form.category_id.data = thread.category_id
    thread_form.content.data = thread.content
    thread_form.submit.label.text = "Edit"

    return render_template("threads/edit.html", thread=thread, form=thread_form)

@thread_blueprint.route("/api/emojis")
def emojis():
    from cps.forum import db

    # Check if emojis exist in the database
    if Emoji.query.count() > 0:
        emojis_list = Emoji.query.all()
        return jsonify([{
            "annotation": e.annotation,
            "emoji": e.emoji,
            "group": e.group,
            "subgroup": e.subgroup,
            "hexcode": e.hexcode,
            "unicode": e.unicode,
            "order": e.order,
            "tags": e.tags,
            "shortcodes": e.shortcodes
        } for e in emojis_list])

    url = "https://emoji.family/api/emojis"

    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
    except requests.RequestException as e:
        log.error(f"Error fetching emojis: {e}")
        return jsonify({"error": "Failed to fetch emojis"}), 500

    emojis_data = response.json()   # list of emoji objects
    new_emojis_response = []

    for e in emojis_data:
        emoji = Emoji(
            annotation=e.get("annotation"),
            emoji=e.get("emoji"),
            group=e.get("group"),
            subgroup=e.get("subgroup"),
            hexcode=e.get("hexcode"),
            unicode=e.get("unicode"),
            order=e.get("order"),
            directional=e.get("directional", False),
            variation=e.get("variation", False),
            emoticons=e.get("emoticons", []),
            shortcodes=e.get("shortcodes", []),
            tags=e.get("tags", []),
            skintone=e.get("skintone"),
            skintone_base=e.get("skintoneBase"),
            skintone_combination=e.get("skintoneCombination"),
            variation_base=e.get("variationBase")
        )

        db.session.add(emoji)
        
        new_emojis_response.append({
            "annotation": e.get("annotation"),
            "emoji": e.get("emoji"),
            "group": e.get("group"),
            "subgroup": e.get("subgroup"),
            "hexcode": e.get("hexcode"),
            "unicode": e.get("unicode"),
            "order": e.get("order"),
            "tags": e.get("tags", []),
            "shortcodes": e.get("shortcodes", [])
        })

    db.session.commit()
    print(f"✅ Inserted {len(emojis_data)} emojis")
    
    return jsonify(new_emojis_response)