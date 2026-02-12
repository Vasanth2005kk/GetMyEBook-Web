# -*- coding: utf-8 -*-

#  This file is part of the Calibre-Web (https://github.com/janeczku/calibre-web)
#    Copyright (C) 2018-2019 OzzieIsaacs, cervinko, jkrehm, bodybybuddha, ok11,
#                            andy29485, idalin, Kyosfonica, wuqi, Kennyl, lemmsh,
#                            falgh1, grunjol, csitko, ytils, xybydy, trasba, vrabe,
#                            ruben-herold, marblepebble, JackED42, SiphonSquirrel,
#                            apetresc, nanu-c, mutschler
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program. If not, see <http://www.gnu.org/licenses/>.
__package__ = "cps"

import sys
import os
import mimetypes

from flask import Flask
from .MyLoginManager import MyLoginManager
from flask_principal import Principal

from . import logger
from .cli import CliParameter
from .constants import CONFIG_DIR
from .reverseproxy import ReverseProxied
from .server import WebServer
from .dep_check import dependency_check
from .updater import Updater
from .babel import babel, get_locale
from . import config_sql
from . import cache_buster
from . import ub, db

# PostgreSQL/SQLAlchemy imports
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv
from .utils import get_env_path



log = logger.create()


# Load .env from project root dynamically
env_path = get_env_path()

if os.path.exists(env_path):
    load_dotenv(env_path)
    log.info(f"Loaded environment variables from: {env_path}")
else:
    log.warning(f".env file not found at {env_path}")

try:
    from flask_limiter import Limiter
    limiter_present = True
except ImportError:
    limiter_present = False
try:
    from flask_wtf.csrf import CSRFProtect
    wtf_present = True
except ImportError:
    wtf_present = False


mimetypes.init()
mimetypes.add_type('application/javascript', '.mjs')
# ... (mimetype definitions remain the same)


app = Flask(__name__)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_SAMESITE='Lax',
    REMEMBER_COOKIE_SAMESITE='Strict',
    WTF_CSRF_SSL_STRICT=False,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_ENGINE_OPTIONS={
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
)
app.config['DEBUG'] = True
lm = MyLoginManager()

cli_param = CliParameter()

config = config_sql.ConfigSQL()

if wtf_present:
    csrf = CSRFProtect()
else:
    csrf = None

calibre_db = db.CalibreDB()

web_server = WebServer()

updater_thread = Updater()

if limiter_present:
    limiter = Limiter(key_func=True, headers_enabled=True, auto_check=False, swallow_errors=False)
else:
    limiter = None

# Global database engine and session
db_engine = None
db_session = None

def create_database_tables(engine):
    """Create all required database tables if they don't exist"""
    try:
        log.info("Creating database tables...")
        
        # Import all models that need to be created
        from . import ub
        from . import config_sql
        
        # Create all tables
        ub.Base.metadata.create_all(engine)
        config_sql._Base.metadata.create_all(engine)
        
        # Create forum tables
        try:
            from cps.forum import db as forum_db
            from cps.forum import init_forum_models
            
            # Import models to register them with metadata
            models = init_forum_models()
            
            # Create forum tables using forum's db
            with app.app_context():
                forum_db.create_all()
                log.info("✅ Forum tables created successfully")
        except ImportError as e:
            log.warning(f"⚠️  Forum models not found, skipping forum table creation: {e}")
        except Exception as e:
            log.error(f"❌ Error creating forum tables: {e}")
        
        log.info("Database tables created successfully")
        
    except Exception as e:
        log.error(f"Error creating database tables: {e}")
        raise

def create_app():
    global db_engine, db_session
    
    if csrf:
        csrf.init_app(app)

    cli_param.init()

    # Ensure PostgreSQL database exists before initializing tables
    try:
        from cps.create_metadata_psql import create_database_if_not_exists
        create_database_if_not_exists()
    except Exception as e:
        log.error(f"Failed to check/create database: {e}")

    ub.init_db()
    # Initialize PostgreSQL database FIRST
    db_engine, db_session = init_postgresql()
    ub.session = db_session
    
    # Configure forum database to use same PostgreSQL connection
    import urllib.parse
    db_password = os.environ.get('DB_PASSWORD', '')
    encoded_password = urllib.parse.quote_plus(db_password)
    forum_db_uri = os.environ.get('DATABASE_URL') or \
        f"postgresql+psycopg2://{os.environ.get('DB_USERNAME')}:{encoded_password}@{os.environ.get('DB_HOST')}:{os.environ.get('DB_PORT')}/{os.environ.get('DATABASENAME_APP')}"
    
    app.config['SQLALCHEMY_DATABASE_URI'] = forum_db_uri
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Load configuration
    encrypt_key, error = config_sql.get_encryption_key(os.path.dirname(cli_param.settings_path))

    config_sql.load_configuration(ub.session, encrypt_key)
    config.init_config(ub.session, encrypt_key, cli_param)

    if error:
        log.error(error)

    # ========================================
    # Initialize Forum Module
    # ========================================
    try:
        log.info("Initializing forum module...")
        
        # Configure mail settings for forum
        app.config.update(
            MAIL_SERVER=os.environ.get('MAIL_SERVER'),
            MAIL_PORT=int(os.environ.get('MAIL_PORT', 587)),
            MAIL_USERNAME=os.environ.get('MAIL_USERNAME'),
            MAIL_PASSWORD=os.environ.get('MAIL_PASSWORD'),
            MAIL_USE_TLS=os.environ.get('MAIL_ENCRYPTION') == 'tls',
            MAIL_USE_SSL=os.environ.get('MAIL_ENCRYPTION') == 'ssl',
            MAIL_DEFAULT_SENDER=os.environ.get('MAIL_DEFAULT_SENDER'),
            APP_NAME=os.environ.get('APP_NAME'),
            AVATAR_FOLDER=os.path.join(app.root_path, 'static/forum/images/avatars'),
        )
        
        # Initialize forum extensions
        from cps.forum import init_forum_extensions, get_forum_blueprints
        init_forum_extensions(app)
        
        # Register forum blueprints (excluding auth - using GetMyEBook login instead)
        blueprints = get_forum_blueprints()
        app.register_blueprint(blueprints['main'], url_prefix='/forum')
        app.register_blueprint(blueprints['threads'], url_prefix='/forum/threads')
        app.register_blueprint(blueprints['comments'], url_prefix='/forum/api')
        app.register_blueprint(blueprints['settings'], url_prefix='/forum/settings')
        # Auth blueprint removed - forum uses GetMyEBook SSO login via auth_bridge
        
        log.info("✅ Forum module initialized successfully")
        # log.info("✅ Forum blueprints registered: /forum, /forum/threads, /forum/api, /forum/settings")
    except ImportError as e:
        log.warning(f"⚠️  Could not import forum module: {e}")
    except Exception as e:
        import traceback
        log.error(f"❌ Failed to initialize forum: {e}")
        log.error(f"Traceback: {traceback.format_exc()}")

    # CREATE DATABASE TABLES
    create_database_tables(db_engine)

    ub.password_change(cli_param.user_credentials)

    if sys.version_info < (3, 0):
        log.info('*** Python2 is EOL since end of 2019, this version of Calibre-Web is no longer supporting Python2, please update your installation to Python3 ***')
        print('*** Python2 is EOL since end of 2019, this version of Calibre-Web is no longer supporting Python2, please update your installation to Python3 ***')
        web_server.stop(True)
        sys.exit(5)

    lm.login_view = 'web.login'
    lm.anonymous_user = ub.Anonymous
    lm.session_protection = 'strong' if config.config_session == 1 else "basic"

    # db.CalibreDB.update_config(config)
    db.CalibreDB.update_config(config, config.config_calibre_dir, cli_param.settings_path)
    
    # Initialize Calibre database with PostgreSQL
    # db.CalibreDB.setup_db(config.config_calibre_dir)
    db.CalibreDB.setup_db(config.config_calibre_dir, cli_param.settings_path)
    calibre_db.init_db()

    updater_thread.init_updater(config, web_server)
    # Perform dry run of updater and exit afterward
    if cli_param.dry_run:
        updater_thread.dry_run()
        sys.exit(0)
    updater_thread.start()
    
    requirements = dependency_check()
    for res in requirements:
        if res['found'] == "not installed":
            message = ('Cannot import {name} module, it is needed to run calibre-web, please install it using "pip install {name}"').format(name=res["name"])
            log.info(message)
            print("*** " + message + " ***")
            web_server.stop(True)
            sys.exit(8)
            
    for res in requirements + dependency_check(True):
        log.info('*** "{}" version does not meet the requirements. Should: {}, Found: {}, please consider installing required version ***'.format(res['name'], res['target'], res['found']))
        
    app.wsgi_app = ReverseProxied(app.wsgi_app)

    if os.environ.get('FLASK_DEBUG'):
        cache_buster.init_cache_busting(app)
        
    log.info('Starting GetMyEBook Web...')
    Principal(app)
    lm.init_app(app)
    app.secret_key = os.environ.get('SECRET_KEY')

    web_server.init_app(app, config)
    if hasattr(babel, "localeselector"):
        babel.init_app(app)
        babel.localeselector(get_locale)
    else:
        babel.init_app(app, locale_selector=get_locale)

    from . import services

    if services.ldap:
        services.ldap.init_app(app, config)
    if services.goodreads_support:
        services.goodreads_support.connect(config.config_goodreads_api_key, config.config_use_goodreads)
        
    config.store_calibre_uuid(calibre_db, db.Library_Id)
    
    # Configure rate limiter
    app.config.update(RATELIMIT_ENABLED=config.config_ratelimiter)
    if config.config_limiter_uri != "" and not cli_param.memory_backend:
        app.config.update(RATELIMIT_STORAGE_URI=config.config_limiter_uri)
        if config.config_limiter_options != "":
            app.config.update(RATELIMIT_STORAGE_OPTIONS=config.config_limiter_options)
            
    try:
        limiter.init_app(app)
    except Exception as e:
        log.error('Wrong Flask Limiter configuration, falling back to default: {}'.format(e))
        app.config.update(RATELIMIT_STORAGE_URI=None)
        limiter.init_app(app)

    # Register scheduled tasks
    from .schedule import register_scheduled_tasks, register_startup_tasks
    register_scheduled_tasks(config.schedule_reconnect)
    register_startup_tasks()
    


    # Add teardown handler for database sessions
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        if db_session:
            db_session.remove()
        if db.CalibreDB.session_factory:
            db.CalibreDB.session_factory.remove()

    return app


def init_postgresql():
    """Initialize PostgreSQL database connection"""
    try:
        # Get database URL from environment variables first
        database_url = os.environ.get('DATABASE_URL')
        
        if not database_url:
            # Get database config from environment variables
            db_user = os.environ.get('DB_USERNAME')
            db_password = os.environ.get('DB_PASSWORD')
            db_host = os.environ.get('DB_HOST')
            db_port = os.environ.get('DB_PORT')
            db_name = os.environ.get('DATABASENAME_APP')
            
            if not all([db_name, db_user, db_password]):
                log.error("Missing required database environment variables")
                log.error("Please ensure DB_USERNAME, DB_PASSWORD, and DATABASENAME_APP are set")
                return None, None
            
            # Properly encode the password for URL
            import urllib.parse
            encoded_password = urllib.parse.quote_plus(db_password)

            database_url = f"postgresql+psycopg2://{db_user}:{encoded_password}@{db_host}:{db_port}/{db_name}"
        
        # log.info(f"Connecting to PostgreSQL database: {database_url.split('@')[1] if '@' in database_url else database_url}")
        
        # Create engine with connection pooling
         # Create engine with connection pooling
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=300,
            echo=False
        )
        
        # Test connection
        with engine.connect() as conn:
            log.info("PostgreSQL connection test successful")
        
        # Create scoped session
        session_factory = sessionmaker(bind=engine)
        session = scoped_session(session_factory)
        
        return engine, session
        
    except Exception as e:
        log.error(f"Failed to initialize PostgreSQL: {e}")
        return None, None




def get_db_session():
    """Get current database session"""
    return db_session


def get_db_engine():
    """Get database engine"""
    return db_engine