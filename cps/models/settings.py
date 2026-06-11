# -*- coding: utf-8 -*-
"""
cps/models/settings.py
-----------------------
SQLAlchemy model definitions for the two core application-settings tables:

  * flask_settings  – stores the Flask session secret key (BYTEA)
  * settings        – stores every other application/mail/Calibre config knob

Both models are declared on a shared ``_Base`` so that ``_Base.metadata`` can
be passed to ``create_all()`` independently of the Calibre-book metadata Base.

Usage
-----
These classes are the single source of truth for the schema.  Both
``cps/config_sql.py`` and ``cps/forum/config.py`` (and any future consumer)
should import from here rather than redefine the tables.
"""

import os

from sqlalchemy import (
    Column, String, Integer, SmallInteger, Boolean, BLOB, JSON, DateTime,
)
from sqlalchemy.dialects.postgresql import BYTEA
from .. import constants, logger
from .base import Base

log = logger.create()

class _Flask_Settings(Base):
    """Stores the Flask session secret key (persisted across restarts)."""

    __tablename__ = 'flask_settings'

    id = Column(Integer, primary_key=True)
    flask_session_key = Column(BYTEA, default=b"")

    def __init__(self, key):
        super().__init__()
        self.flask_session_key = key


class _Settings(Base):
    """
    Every application, mail, Calibre, LDAP and schedule configuration knob.

    Rows are loaded on startup by ``cps.config_sql.ConfigSQL`` and written
    back whenever the admin saves the settings page.
    """

    __tablename__ = 'settings'

    id = Column(Integer, primary_key=True)

    # ── Mail ─────────────────────────────────────────────────────────────
    mail_server = Column(String, default=constants.DEFAULT_MAIL_SERVER)
    mail_port = Column(Integer, default=25)
    mail_use_ssl = Column(SmallInteger, default=0)
    mail_login = Column(String, default='mail@example.com')
    mail_password_e = Column(String)
    mail_password = Column(String)
    mail_from = Column(String, default='automailer <mail@example.com>')
    mail_size = Column(Integer, default=25 * 1024 * 1024)
    mail_server_type = Column(SmallInteger, default=0)
    mail_gmail_token = Column(JSON, default={})

    # ── Calibre library ──────────────────────────────────────────────────
    config_calibre_dir = Column(String, default=os.environ.get('BOOK_FILEPATH'))
    config_calibre_uuid = Column(String)
    config_calibre_split = Column(Boolean, default=False)
    config_calibre_split_dir = Column(String)

    # ── Web server ───────────────────────────────────────────────────────
    config_port = Column(Integer, default=constants.DEFAULT_PORT)
    config_external_port = Column(Integer, default=constants.DEFAULT_PORT)
    config_certfile = Column(String)
    config_keyfile = Column(String)
    config_trustedhosts = Column(String, default='')
    config_calibre_web_title = Column(String, default='Calibre-Web')

    # ── Books / UI ───────────────────────────────────────────────────────
    config_books_per_page = Column(Integer, default=60)
    config_random_books = Column(Integer, default=4)
    config_authors_max = Column(Integer, default=0)
    config_read_column = Column(Integer, default=0)
    config_title_regex = Column(
        String,
        default=(
            r'^(A|The|An|Der|Die|Das|Den|Ein|Eine'
            r'|Einen|Dem|Des|Einem|Eines|Le|La|Les|L\'|Un|Une)\s+'
        ),
    )
    config_theme = Column(Integer, default=0)

    # ── Logging ──────────────────────────────────────────────────────────
    config_log_level = Column(SmallInteger, default=logger.DEFAULT_LOG_LEVEL)
    config_logfile = Column(String, default=logger.DEFAULT_LOG_FILE)
    config_access_log = Column(SmallInteger, default=0)
    config_access_logfile = Column(String, default=logger.DEFAULT_ACCESS_LOG)

    # ── Registration / access ────────────────────────────────────────────
    config_uploading = Column(SmallInteger, default=1)
    config_anonbrowse = Column(SmallInteger, default=1)
    config_public_reg = Column(SmallInteger, default=1)
    config_remote_login = Column(Boolean, default=False)
    config_kobo_sync = Column(Boolean, default=False)

    # ── Default user settings ────────────────────────────────────────────
    config_default_role = Column(SmallInteger, default=0)
    config_default_show = Column(Integer, default=constants.ADMIN_USER_SIDEBAR)
    config_default_language = Column(String(3), default="all")
    config_default_locale = Column(String(2), default="en")
    config_columns_to_ignore = Column(String)

    # ── Tag / content filtering ──────────────────────────────────────────
    config_denied_tags = Column(String, default="")
    config_allowed_tags = Column(String, default="")
    config_restricted_column = Column(SmallInteger, default=0)
    config_denied_column_value = Column(String, default="")
    config_allowed_column_value = Column(String, default="")

    # Google Drive settings removed

    # ── Goodreads ────────────────────────────────────────────────────────
    config_use_goodreads = Column(Boolean, default=False)
    config_goodreads_api_key = Column(String)
    config_register_email = Column(Boolean, default=True)
    config_login_type = Column(Integer, default=2)

    # ── Kobo proxy ───────────────────────────────────────────────────────
    config_kobo_proxy = Column(Boolean, default=False)

    # ── LDAP ─────────────────────────────────────────────────────────────
    config_ldap_provider_url = Column(String, default='example.org')
    config_ldap_port = Column(SmallInteger, default=389)
    config_ldap_authentication = Column(SmallInteger, default=constants.LDAP_AUTH_SIMPLE)
    config_ldap_serv_username = Column(String, default='cn=admin,dc=example,dc=org')
    config_ldap_serv_password_e = Column(String)
    config_ldap_serv_password = Column(String)
    config_ldap_encryption = Column(SmallInteger, default=0)
    config_ldap_cacert_path = Column(String, default="")
    config_ldap_cert_path = Column(String, default="")
    config_ldap_key_path = Column(String, default="")
    config_ldap_dn = Column(String, default='dc=example,dc=org')
    config_ldap_user_object = Column(String, default='uid=%s')
    config_ldap_member_user_object = Column(String, default='')
    config_ldap_openldap = Column(Boolean, default=True)
    config_ldap_group_object_filter = Column(String, default='(&(objectclass=posixGroup)(cn=%s))')
    config_ldap_group_members_field = Column(String, default='memberUid')
    config_ldap_group_name = Column(String, default='calibreweb')

    # ── Converters / external tools ──────────────────────────────────────
    config_kepubifypath = Column(String, default=None)
    config_converterpath = Column(String, default=None)
    config_binariesdir = Column(String, default=None)
    config_calibre = Column(String)
    config_rarfile_location = Column(String, default=None)
    config_upload_formats = Column(String, default=','.join(constants.EXTENSIONS_UPLOAD))
    config_unicode_filename = Column(Boolean, default=False)
    config_embed_metadata = Column(Boolean, default=True)

    # ── Update channel ───────────────────────────────────────────────────
    config_updatechannel = Column(Integer, default=constants.UPDATE_STABLE)

    # ── Reverse-proxy login ──────────────────────────────────────────────
    config_reverse_proxy_login_header_name = Column(String)
    config_allow_reverse_proxy_header_login = Column(Boolean, default=False)

    # ── Scheduler ────────────────────────────────────────────────────────
    schedule_start_time = Column(Integer, default=4)
    schedule_duration = Column(Integer, default=10)
    schedule_generate_book_covers = Column(Boolean, default=False)
    schedule_generate_series_covers = Column(Boolean, default=False)
    schedule_reconnect = Column(Boolean, default=False)
    schedule_metadata_backup = Column(Boolean, default=False)

    # ── Password policy ──────────────────────────────────────────────────
    config_password_policy = Column(Boolean, default=True)
    config_password_min_length = Column(Integer, default=8)
    config_password_number = Column(Boolean, default=True)
    config_password_lower = Column(Boolean, default=True)
    config_password_upper = Column(Boolean, default=True)
    config_password_character = Column(Boolean, default=True)
    config_password_special = Column(Boolean, default=True)

    # ── Session / rate-limiting ──────────────────────────────────────────
    config_session = Column(Integer, default=1)
    config_ratelimiter = Column(Boolean, default=True)
    config_limiter_uri = Column(String, default="")
    config_limiter_options = Column(String, default="")
    config_check_extensions = Column(Boolean, default=True)

    # ── PostgreSQL connection ─────────────────────────────────────────────
    config_db_host = Column(String, default='localhost')
    config_db_port = Column(String, default='5432')
    config_db_name = Column(String, default='getmyebook_app')
    config_db_user = Column(String, default='vasanth')
    config_db_password_e = Column(String)
    config_db_password = Column(String)
    config_database_url = Column(String)
    config_use_postgresql = Column(Boolean, default=False)

    # ── PostgreSQL metadata ──────────────────────────────────────────────
    config_use_postgresql_metadata = Column(Boolean, default=False)
    config_postgresql_metadata_url = Column(String)

    # ── AWS S3 service toggle ─────────────────────────────────────────────
    aws_active = Column(Boolean, default=True)
    aws_enabled_at = Column(DateTime, default=None, nullable=True)
    aws_disabled_at = Column(DateTime, default=None, nullable=True)

    def __repr__(self):
        return self.__class__.__name__



def load_settings(session):
    """
    Return the first ``_Settings`` row, creating a default one if the table
    is empty.  Intended for use by both ``config_sql.ConfigSQL`` and
    ``cps/forum/config.py``.

    Parameters
    ----------
    session : sqlalchemy.orm.Session
        An active, bound session (e.g. ``ub.session`` from ``cps.models.ub``).

    Returns
    -------
    _Settings
    """
    try:
        row = session.query(_Settings).first()
        if row is None:
            log.warning("No settings row found – inserting defaults.")
            row = _Settings()
            session.add(row)
            session.commit()
        return row
    except Exception as exc:
        log.error("Could not load settings from database: %s", exc)
        return _Settings()  # in-memory default, not persisted


def load_flask_settings(session):
    """
    Return the first ``_Flask_Settings`` row, creating a default one if empty.
    """
    try:
        row = session.query(_Flask_Settings).first()
        if row is None:
            log.warning("No flask_settings row found – inserting empty key.")
            row = _Flask_Settings(b"")
            session.add(row)
            session.commit()
        return row
    except Exception as exc:
        log.error("Could not load flask_settings from database: %s", exc)
        return _Flask_Settings(b"")
