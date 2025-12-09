"""
Forum Context Processor
Injects forum-specific variables into all forum templates
"""
from flask import request
from flask_login import current_user
from cps.forum.database.models.category import Category
from cps.forum.auth_bridge import get_forum_user
import logging

log = logging.getLogger('cps.forum.context_processor')

def inject_forum_context():
    """
    Context processor to inject forum-specific variables into templates
    This makes categories available in all forum templates
    """
    context = {}
    
    # Only apply to forum routes
    if not request.path.startswith('/forum'):
        return context
    
    # Inject categories for navbar dropdown
    try:
        categories = Category.query.all()
        context['app_categories'] = categories
    except Exception as e:
        log.error(f"Error loading categories: {e}")
        context['app_categories'] = []
    
    # Ensure user has forum fields initialized if authenticated
    if current_user.is_authenticated:
        try:
            user = get_forum_user()  # This will auto-initialize forum fields
            if not user:
                log.warning("Could not get forum user for authenticated user")
        except Exception as e:
            log.error(f"Error getting forum user: {e}")
            import traceback
            log.error(traceback.format_exc())
    
    return context

