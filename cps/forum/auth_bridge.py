"""
Authentication Bridge between Calibre-Web Users and Forum
Simplified - now uses main User model directly (no separate forum_users table)
"""
from flask_login import current_user
from cps import ub
import logging

log = logging.getLogger('cps.forum.auth_bridge')

def get_forum_user():
    """
    Get current user for forum (same as GetMyEBook user)
    No longer needs to create/sync separate forum user
    
    Returns:
        User: Current authenticated user or None
    """
    if not current_user.is_authenticated:
        log.debug("User not authenticated, returning None")
        return None
    
    # Ensure user has forum avatar set
    if not current_user.forum_avatar:
        current_user.forum_avatar = "avatar.png"
        try:
            ub.session.commit()
        except Exception as e:
            log.error(f"Error setting default avatar: {e}")
            ub.session.rollback()
    
    # Auto-verify email for forum if not already verified
    if not current_user.forum_email_verified_at and current_user.email:
        from datetime import datetime
        current_user.forum_email_verified_at = datetime.utcnow()
        try:
            ub.session.commit()
            log.info(f"Auto-verified forum email for user: {current_user.name}")
        except Exception as e:
            log.error(f"Error auto-verifying email: {e}")
            ub.session.rollback()
    
    return current_user

def get_forum_user_id():
    """
    Get forum user ID for current Calibre user
    Helper function for templates and routes
    
    Returns:
        int: User ID or None
    """
    user = get_forum_user()
    return user.id if user else None

# Backward compatibility aliases
get_or_create_forum_user = get_forum_user

__all__ = [
    'get_forum_user',
    'get_or_create_forum_user',  # Backward compatibility
    'get_forum_user_id'
]
