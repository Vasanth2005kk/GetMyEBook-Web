"""
Flask Forum Module 
Integrated with GetMyEBook-Web (Calibre-Web)
"""
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_mail import Mail
from flask_marshmallow import Marshmallow
from flask_migrate import Migrate

# Flask-Modus is optional (has compatibility issues with newer Werkzeug)
try:
    from flask_modus import Modus
    modus_available = True
except ImportError:
    modus_available = False
    Modus = None

# Flask-Seeder is optional
try:
    from flask_seeder import FlaskSeeder
    seeder_available = True
except ImportError:
    seeder_available = False
    FlaskSeeder = None

# Initialize extensions (will be bound to app in cps/__init__.py)
db = SQLAlchemy()
migrate = Migrate()
bcrypt = Bcrypt()
mail = Mail()
ma = Marshmallow()
modus = Modus() if modus_available and Modus else None
seeder = FlaskSeeder() if seeder_available and FlaskSeeder else None

# These will be imported after extensions are initialized
# Import happens in init_forum_models() to avoid circular imports

def init_forum_extensions(app):
    """Initialize forum extensions with Flask app"""
    db.init_app(app)
    migrate.init_app(app, db)
    bcrypt.init_app(app)
    mail.init_app(app)
    ma.init_app(app)
    if modus_available and modus:
        modus.init_app(app)
    if seeder_available and seeder:
        seeder.init_app(app, db)
    
    # Register context processor for forum templates
    from cps.forum.context_processor import inject_forum_context
    app.context_processor(inject_forum_context)

    # Register markdown filter
    try:
        import markdown
        import bleach
        
        def markdown_filter(text):
            allowed_tags = bleach.sanitizer.ALLOWED_TAGS + [
                'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
                'p', 'br', 'hr', 'pre', 'code', 
                'ul', 'ol', 'li', 'blockquote', 
                'table', 'thead', 'tbody', 'tr', 'th', 'td',
                'img', 'span', 'div'
            ]
            allowed_attrs = dict(bleach.sanitizer.ALLOWED_ATTRIBUTES)
            allowed_attrs.update({
                'img': ['src', 'alt', 'title', 'width', 'height'],
                '*': ['class', 'style', 'id']
            })
            
            # Convert markdown to html
            html = markdown.markdown(
                text, 
                extensions=['fenced_code', 'tables', 'nl2br']
            )
            
            # Sanitize html
            return bleach.clean(
                html, 
                tags=allowed_tags, 
                attributes=allowed_attrs, 
                strip=True
            )
            
        app.jinja_env.filters['markdown'] = markdown_filter
    except ImportError:
        # Fallback if markdown/bleach not available
        app.jinja_env.filters['markdown'] = lambda text: text

def get_forum_blueprints():
    """Get forum blueprints for registration (auth excluded - using GetMyEBook SSO)"""
    # Auth blueprint removed - forum uses GetMyEBook login via auth_bridge
    from cps.forum.apps.main.routes import main_blueprint
    from cps.forum.apps.threads.routes import thread_blueprint
    from cps.forum.apps.comments.routes import comments_blueprint
    from cps.forum.apps.settings.routes import settings_blueprint
    
    return {
        'main': main_blueprint,
        'threads': thread_blueprint,
        'comments': comments_blueprint,
        'settings': settings_blueprint
    }

def init_forum_models():
    """Import forum models after db is initialized"""
    from cps.forum.database.models import Thread, Comment, Category
    from cps.ub import User  # User comes from main app
    return {'User': User, 'Thread': Thread, 'Comment': Comment, 'Category': Category}

__all__ = [
    'db', 'migrate', 'bcrypt', 'mail', 'ma', 'modus', 'seeder',
    'init_forum_extensions', 'get_forum_blueprints', 'init_forum_models'
]
