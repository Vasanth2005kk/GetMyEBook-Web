from flask import Blueprint, render_template, request
from cps.forum.database.models.thread import Thread
from cps.forum.database.models.comment import Comment
from sqlalchemy.orm import joinedload
from flask import abort
main_blueprint = Blueprint('main', __name__, template_folder='../../templates')


@main_blueprint.route('/')
def index():

    threads = Thread.query\
        .options(joinedload(Thread.category))\
        .options(joinedload(Thread.comments))\

    page = request.args.get('page', 1, type=int)
    primary_filter = 'recent' if request.args.get('popular') is None else 'popular'

    if primary_filter == 'popular':
        threads = threads.order_by(Thread.views_count.desc())
    else:
        threads = threads.order_by(Thread.created_at.desc())

    secondary_filter = 'all' if request.args.get('filter') is None else request.args.get('filter')
    if secondary_filter is not None:
        if secondary_filter == 'answered':
            threads = threads.filter(Thread.comments_count > 0)

        if secondary_filter == 'unanswered':
            threads = threads.filter(Thread.comments_count == 0)

    threads = threads.paginate(page=page, per_page=10, error_out=False)
    # return abort(404)
    return render_template('main/index.html',
                           threads=threads,
                           primary_filter=primary_filter,
                           secondary_filter=secondary_filter
                           )


@main_blueprint.route('/about-us')
def about():
    return render_template('main/about-us.html')


@main_blueprint.route('/search')
def search():
    q = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)

    threads = Thread.query.options(joinedload(Thread.category)).options(joinedload(Thread.comments))

    if q:
        from sqlalchemy import or_
        threads = threads.filter(
            or_(
                Thread.title.ilike(f'%{q}%'),
                Thread.content.ilike(f'%{q}%')
            )
        )

    # Apply default sorting (recent)
    threads = threads.order_by(Thread.created_at.desc())

    # Pagination
    threads = threads.paginate(page=page, per_page=10, error_out=False)

    return render_template('main/index.html',
                           threads=threads,
                           primary_filter='recent',
                           secondary_filter='all',
                           search_query=q
                           )