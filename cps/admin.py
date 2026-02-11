# -*- coding: utf-8 -*-

#  This file is part of the Calibre-Web (https://github.com/janeczku/calibre-web)
#    Copyright (C) 2018-2019 OzzieIsaacs, cervinko, jkrehm, bodybybuddha, ok11,
#                            andy29485, idalin, Kyosfonica, wuqi, Kennyl, lemmsh,
#                            falgh1, grunjol, csitko, ytils, xybydy, trasba, vrabe,
#                            ruben-herold, marblepebble, JackED42, SiphonSquirrel,
#                            apetresc, nanu-c, mutschler, GammaC0de, vuolter
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

import os
import re
import json
import operator
import time
import sys
import string
from datetime import datetime, timedelta
from datetime import time as datetime_time
from functools import wraps
from urllib.parse import urlparse
from xml.etree.ElementTree import Comment

from flask import Blueprint, flash, redirect, url_for, abort, request, make_response, send_from_directory, g, Response
from markupsafe import Markup
from .cw_login import current_user
from flask_babel import gettext as _
from flask_babel import get_locale, format_time, format_datetime, format_timedelta
from sqlalchemy import and_
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.exc import IntegrityError, OperationalError, InvalidRequestError
from sqlalchemy.sql.expression import func, or_, text

from . import constants, logger, helper, services, cli_param
from . import db, calibre_db, ub, web_server, config, updater_thread, gdriveutils, \
    kobo_sync_status, schedule
from .helper import check_valid_domain, send_test_mail, reset_password, generate_password_hash, check_email, \
    valid_email, check_username
from .embed_helper import get_calibre_binarypath
from .gdriveutils import is_gdrive_ready, gdrive_support
from .render_template import render_title_template, get_sidebar_config
from .services.worker import WorkerThread
from .usermanagement import user_login_required
from .babel import get_available_translations, get_available_locale, get_user_locale_language
from . import debug_info
from .utils import get_env_path 
import urllib

log = logger.create()

feature_support = {
    'ldap': bool(services.ldap),
    'goodreads': bool(services.goodreads_support),
    'kobo': bool(services.kobo),
    'updater': constants.UPDATER_AVAILABLE,
    'gmail': bool(services.gmail),
    'scheduler': schedule.use_APScheduler,
    'gdrive': gdrive_support,
    'oauth': True  # Always True since we're using Authlib
}

try:
    #import rarfile  # pylint: disable=unused-import
    feature_support['rar'] = True
except (ImportError, SyntaxError):
    feature_support['rar'] = False

try:
    from .oauth_bb import oauth_check, oauthblueprints
except ImportError as err:
    log.debug('Cannot import OAuth module: %s', err)
    oauthblueprints = []
    oauth_check = {}

admi = Blueprint('admin', __name__)

def admin_required(f):
    """
    Checks if current_user.role == 1
    """
    @wraps(f)
    def inner(*args, **kwargs):
        if current_user.role_admin():
            return f(*args, **kwargs)
        abort(403)
    return inner

@admi.before_app_request
def before_request():
    g.constants = constants
    g.google_site_verification = os.getenv('GOOGLE_SITE_VERIFICATION', '')
    g.allow_registration = config.config_public_reg
    g.allow_anonymous = config.config_anonbrowse
    g.allow_upload = 1 #config.config_uploading
    g.current_theme = config.config_theme
    g.config_authors_max = config.config_authors_max
    if '/static/' not in request.path and not config.db_configured and \
        request.endpoint not in ('admin.ajax_db_config',
                                 'admin.simulatedbchange',
                                 'admin.db_configuration',
                                 'web.login',
                                 'web.login_post',
                                 'web.logout',
                                 'auth.login',
                                 'auth.register',
                                 'auth.logout',
                                 'admin.load_dialogtexts',
                                 'admin.ajax_pathchooser'):
        return redirect(url_for('admin.db_configuration'))

@admi.route("/shutdown", methods=["POST"])
@user_login_required
@admin_required
def shutdown():
    task = request.get_json().get('parameter', -1)
    show_text = {}
    if task in (0, 1):  # valid commandos received
        # close all database connections
        calibre_db.dispose()
        ub.dispose()

        if task == 0:
            show_text['text'] = _('Server restarted, please reload page.')
        else:
            show_text['text'] = _('Performing Server shutdown, please close window.')
        # stop gevent/tornado server
        web_server.stop(task == 0)
        return json.dumps(show_text)

    if task == 2:
        log.warning("reconnecting to calibre database")
        calibre_db.reconnect_db(config, ub.app_DB_path)
        show_text['text'] = _('Success! Database Reconnected')
        return json.dumps(show_text)

    show_text['text'] = _('Unknown command')
    return json.dumps(show_text), 400

@admi.route("/metadata_backup", methods=["POST"])
@user_login_required
@admin_required
def queue_metadata_backup():
    show_text = {}
    log.warning("Queuing all books for metadata backup")
    helper.set_all_metadata_dirty()
    show_text['text'] = _('Success! Books queued for Metadata Backup, please check Tasks for result')
    return json.dumps(show_text)

# method is available without login and not protected by CSRF to make it easy reachable, is per default switched off
# needed for docker applications, as changes on metadata.db from host are not visible to application
@admi.route("/reconnect", methods=['GET'])
def reconnect():
    if cli_param.reconnect_enable:
        calibre_db.reconnect_db(config, ub.app_DB_path)
        return json.dumps({})
    else:
        log.debug("'/reconnect' was accessed but is not enabled")
        abort(404)

@admi.route("/ajax/updateThumbnails", methods=['POST'])
@admin_required
@user_login_required
def update_thumbnails():
    content = config.get_scheduled_task_settings()
    if content['schedule_generate_book_covers']:
        log.info("Update of Cover cache requested")
        helper.update_thumbnail_cache()
    return ""

@admi.route("/admin/view")
@user_login_required
@admin_required
def admin():
    version = updater_thread.get_current_version_info()
    if version is False:
        commit = _('Unknown')
    else:
        if 'datetime' in version:
            commit = version['datetime']
            tz = timedelta(seconds=time.timezone if (time.localtime().tm_isdst == 0) else time.altzone)
            form_date = datetime.strptime(commit[:19], "%Y-%m-%dT%H:%M:%S")
            if len(commit) > 19:  # check if string has timezone
                if commit[19] == '+':
                    form_date -= timedelta(hours=int(commit[20:22]), minutes=int(commit[23:]))
                elif commit[19] == '-':
                    form_date += timedelta(hours=int(commit[20:22]), minutes=int(commit[23:]))
            commit = format_datetime(form_date - tz, format='short')
        else:
            commit = version['version'].replace("b", " Beta")

    all_user = ub.session.query(ub.User).all()
    schedule_time = format_time(datetime_time(hour=config.schedule_start_time), format="short")
    t = timedelta(hours=config.schedule_duration // 60, minutes=config.schedule_duration % 60)
    schedule_duration = format_timedelta(t, threshold=.99)

    return render_title_template("admin.html", allUser=all_user, config=config, commit=commit,
                                 feature_support=feature_support, schedule_time=schedule_time,
                                 schedule_duration=schedule_duration,
                                 title=_("Admin page"), page="admin")


# Admin-only comments management panel
@admi.route("/admin/comments/delete", methods=["POST"])
@user_login_required
@admin_required
def delete_comment_admin():
    from cps.forum.database.models import Comment
    from cps.forum import db as forum_db
    
    try:
        comment_id = request.form.get("comment_id")
        if not comment_id:
             return json.dumps({"success": False, "message": _("No comment ID provided")}), 400

        comment = forum_db.session.query(Comment).filter(Comment.id == comment_id).first()
        if comment:
            forum_db.session.delete(comment)
            forum_db.session.commit()
            return json.dumps({"success": True, "message": _("Comment deleted")})
        else:
            return json.dumps({"success": False, "message": _("Comment not found")}), 404
    except Exception as e:
        log.error(f"Error deleting comment: {e}")
        return json.dumps({"success": False, "message": _("An error occurred")}), 500

@admi.route("/admin/comments/edit", methods=["POST"])
@user_login_required
@admin_required
def edit_comment_admin():
    from cps.forum.database.models import Comment
    from cps.forum import db as forum_db

    try:
        # Check if x-editable sent parameters
        # x-editable sends: name, value, pk
        pk = request.form.get("pk")
        value = request.form.get("value")
        
        # Fallback for manual calls
        comment_id = pk or request.form.get("comment_id")
        new_content = value or request.form.get("content")

        if not comment_id or new_content is None:
            return json.dumps({"success": False, "message": _("Missing data")}), 400

        comment = forum_db.session.query(Comment).filter(Comment.id == comment_id).first()
        if comment:
            comment.content = new_content
            forum_db.session.commit()
            return json.dumps({"success": True, "message": _("Comment updated")})
        else:
             return json.dumps({"success": False, "message": _("Comment not found")}), 404
    except Exception as e:
        log.error(f"Error editing comment: {e}")
        return json.dumps({"success": False, "message": _("An error occurred")}), 500

@admi.route("/admin/comments-panel",methods=["GET"])
@user_login_required
@admin_required
def comments_panel():
    from cps.forum.database.models import Comment , Thread
    from cps.forum import db as forum_db

    all_comments = forum_db.session.query(Comment).all()
    
    log.info(f"Access for all comments :{len(all_comments)} comments found")
    panel_datas = {}
    for comment in all_comments:
        dt = comment.created_at
        # log.info(f"Date : {dt.strftime('%d-%m-%Y')} | Time : {dt.strftime('%I:%M:%S %p')}")
        panel_datas[comment.id] = {
            "date": dt.strftime("%d-%m-%Y") if dt else "",
            "time": dt.strftime("%I:%M:%S %p") if dt else "",
            "username": ub.session.query(ub.User).filter(ub.User.id == comment.user_id).first().name if comment.user_id else _("Anonymous"),
            "book_name": forum_db.session.query(Thread).filter(Thread.id == comment.thread_id).first().title if comment.thread_id else _("Unknown"),
            "comment": comment.content if comment.content else "",
        }

    # log.info(f"comments panel datas {panel_datas}")
    return render_title_template("comments_panel.html", 
                                 title=_("Comments Management"), 
                                 page="comments-panel",
                                 panel_datas=panel_datas)
@admi.route("/admin/dbconfig", methods=["GET", "POST"])
@user_login_required
@admin_required
def db_configuration():
    if request.method == "POST":
        log.info(f"/admin/dbconfig post method ==> working !!!  and request data :{request.form.to_dict()}")
        return _db_configuration_update_helper()
    return _db_configuration_result()

@admi.route("/admin/config", methods=["GET"])
@user_login_required
@admin_required
def configuration():
    log.info(f"full admin Config : {config}")
    log.info(f"feature_supports : {feature_support}")
    return render_title_template("config_edit.html",
                                 config=config,
                                 provider=oauthblueprints,
                                 feature_support=feature_support,
                                 title=_("Basic Configuration"), page="config")

@admi.route("/admin/ajaxconfig", methods=["POST"])
@user_login_required
@admin_required
def ajax_config():
    return _configuration_update_helper()

@admi.route("/admin/ajaxdbconfig", methods=["POST"])
@user_login_required
@admin_required
def ajax_db_config():
    return _db_configuration_update_helper()

@admi.route("/admin/alive", methods=["GET"])
@user_login_required
@admin_required
def calibreweb_alive():
    return "", 200

@admi.route("/admin/viewconfig")
@user_login_required
@admin_required
def view_configuration():
    read_column = calibre_db.session.query(db.CustomColumns) \
        .filter(and_(db.CustomColumns.datatype == 'bool', db.CustomColumns.mark_for_delete == False)).all()
    restrict_columns = calibre_db.session.query(db.CustomColumns) \
        .filter(and_(db.CustomColumns.datatype == 'text', db.CustomColumns.mark_for_delete == False)).all()
    languages = calibre_db.speaking_language()
    translations = get_available_locale()
    return render_title_template("config_view_edit.html", conf=config, readColumns=read_column,
                                 restrictColumns=restrict_columns,
                                 languages=languages,
                                 translations=translations,
                                 title=_("UI Configuration"), page="uiconfig")

@admi.route("/admin/usertable")
@user_login_required
@admin_required
def edit_user_table():
    visibility = current_user.view_settings.get('useredit', {})
    languages = calibre_db.speaking_language()
    translations = get_available_locale()
    all_user = ub.session.query(ub.User)
    tags = calibre_db.session.query(db.Tags) \
        .join(db.books_tags_link) \
        .join(db.Books) \
        .filter(calibre_db.common_filters()) \
        .group_by(db.Tags.id) \
        .order_by(db.Tags.name).all()
    if config.config_restricted_column:
        custom_values = calibre_db.session.query(db.cc_classes[config.config_restricted_column]).all()
    else:
        custom_values = []
    if not config.config_anonbrowse:
        all_user = all_user.filter(ub.User.role.op('&')(constants.ROLE_ANONYMOUS) != constants.ROLE_ANONYMOUS)
    kobo_support = feature_support['kobo'] and config.config_kobo_sync
    return render_title_template("user_table.html",
                                 users=all_user.all(),
                                 tags=tags,
                                 custom_values=custom_values,
                                 translations=translations,
                                 languages=languages,
                                 visiblility=visibility,
                                 all_roles=constants.ALL_ROLES,
                                 kobo_support=kobo_support,
                                 sidebar_settings=constants.sidebar_settings,
                                 title=_("Edit Users"),
                                 page="usertable")

@admi.route("/ajax/listusers")
@user_login_required
@admin_required
def list_users():
    off = int(request.args.get("offset") or 0)
    limit = int(request.args.get("limit") or 10)
    search = request.args.get("search")
    sort = request.args.get("sort", "id")
    state = None
    if sort == "state":
        state = json.loads(request.args.get("state", "[]"))
    else:
        if sort not in ub.User.__table__.columns.keys():
            sort = "id"
    order = request.args.get("order", "").lower()

    if sort != "state" and order:
        order = text(sort + " " + order)
    elif not state:
        order = ub.User.id.asc()

    all_user = ub.session.query(ub.User)
    if not config.config_anonbrowse:
        all_user = all_user.filter(ub.User.role.op('&')(constants.ROLE_ANONYMOUS) != constants.ROLE_ANONYMOUS)

    total_count = filtered_count = all_user.count()

    if search:
        all_user = all_user.filter(or_(func.lower(ub.User.name).ilike("%" + search + "%"),
                                       func.lower(ub.User.kindle_mail).ilike("%" + search + "%"),
                                       func.lower(ub.User.email).ilike("%" + search + "%")))
    if state:
        users = calibre_db.get_checkbox_sorted(all_user.all(), state, off, limit, request.args.get("order", "").lower())
    else:
        users = all_user.order_by(order).offset(off).limit(limit).all()
    if search:
        filtered_count = len(users)

    for user in users:
        if user.default_language == "all":
            user.default = _("All")
        else:
            user.default = get_user_locale_language(user.default_language)

    table_entries = {'totalNotFiltered': total_count, 'total': filtered_count, "rows": users}
    js_list = json.dumps(table_entries, cls=db.AlchemyEncoder)
    response = make_response(js_list)
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response

@admi.route("/ajax/deleteuser", methods=['POST'])
@user_login_required
@admin_required
def delete_user():
    user_ids = request.form.to_dict(flat=False)
    users = None
    message = ""
    if "userid[]" in user_ids:
        users = ub.session.query(ub.User).filter(ub.User.id.in_(user_ids['userid[]'])).all()
    elif "userid" in user_ids:
        users = ub.session.query(ub.User).filter(ub.User.id == user_ids['userid'][0]).all()
    count = 0
    errors = list()
    success = list()
    if not users:
        log.error("User not found")
        return Response(json.dumps({'type': "danger", 'message': _("User not found")}), mimetype='application/json')
    for user in users:
        try:
            message = _delete_user(user)
            count += 1
        except Exception as ex:
            log.error(ex)
            errors.append({'type': "danger", 'message': str(ex)})

    if count == 1:
        log.info("User {} deleted".format(user_ids))
        success = [{'type': "success", 'message': message}]
    elif count > 1:
        log.info("Users {} deleted".format(user_ids))
        success = [{'type': "success", 'message': _("{} users deleted successfully").format(count)}]
    success.extend(errors)
    return Response(json.dumps(success), mimetype='application/json')

@admi.route("/ajax/getlocale")
@user_login_required
@admin_required
def table_get_locale():
    locale = get_available_locale()
    ret = list()
    current_locale = get_locale()
    for loc in locale:
        ret.append({'value': str(loc), 'text': loc.get_language_name(current_locale)})
    return json.dumps(ret)

@admi.route("/ajax/getdefaultlanguage")
@user_login_required
@admin_required
def table_get_default_lang():
    languages = calibre_db.speaking_language()
    ret = list()
    ret.append({'value': 'all', 'text': _('Show All')})
    for lang in languages:
        ret.append({'value': lang.lang_code, 'text': lang.name})
    return json.dumps(ret)

@admi.route("/ajax/editlistusers/<param>", methods=['POST'])
@user_login_required
@admin_required
def edit_list_user(param):
    vals = request.form.to_dict(flat=False)
    all_user = ub.session.query(ub.User)
    if not config.config_anonbrowse:
        all_user = all_user.filter(ub.User.role.op('&')(constants.ROLE_ANONYMOUS) != constants.ROLE_ANONYMOUS)
    # only one user is posted
    if "pk" in vals:
        users = [all_user.filter(ub.User.id == vals['pk'][0]).one_or_none()]
    else:
        if "pk[]" in vals:
            users = all_user.filter(ub.User.id.in_(vals['pk[]'])).all()
        else:
            return _("Malformed request"), 400
    if 'field_index' in vals:
        vals['field_index'] = vals['field_index'][0]
    if 'value' in vals:
        vals['value'] = vals['value'][0]
    elif not ('value[]' in vals):
        return _("Malformed request"), 400
    for user in users:
        try:
            if param in ['denied_tags', 'allowed_tags', 'allowed_column_value', 'denied_column_value']:
                if 'value[]' in vals:
                    setattr(user, param, prepare_tags(user, vals['action'][0], param, vals['value[]']))
                else:
                    setattr(user, param, vals['value'].strip())
            else:
                vals['value'] = vals['value'].strip()
                if param == 'name':
                    if user.name == "Guest":
                        raise Exception(_("Guest Name can't be changed"))
                    user.name = check_username(vals['value'])
                elif param == 'email':
                    user.email = check_email(vals['value'])
                elif param == 'kobo_only_shelves_sync':
                    user.kobo_only_shelves_sync = int(vals['value'] == 'true')
                elif param == 'kindle_mail':
                    user.kindle_mail = valid_email(vals['value']) if vals['value'] else ""
                elif param.endswith('role'):
                    value = int(vals['field_index'])
                    if user.name == "Guest" and value in \
                      [constants.ROLE_ADMIN, constants.ROLE_PASSWD, constants.ROLE_EDIT_SHELFS]:
                        raise Exception(_("Guest can't have this role"))
                    # check for valid value, last on checks for power of 2 value
                    if value > 0 and value <= constants.ROLE_VIEWER and (value & value - 1 == 0 or value == 1):
                        if vals['value'] == 'true':
                            user.role |= value
                        elif vals['value'] == 'false':
                            if value == constants.ROLE_ADMIN:
                                if not ub.session.query(ub.User). \
                                    filter(ub.User.role.op('&')(constants.ROLE_ADMIN) == constants.ROLE_ADMIN,
                                           ub.User.id != user.id).count():
                                    return Response(
                                        json.dumps([{'type': "danger",
                                                     'message': _("No admin user remaining, can't remove admin role",
                                                                  nick=user.name)}]), mimetype='application/json')
                            user.role &= ~value
                        else:
                            raise Exception(_("Value has to be true or false"))
                    else:
                        raise Exception(_("Invalid role"))
                elif param.startswith('sidebar'):
                    value = int(vals['field_index'])
                    if user.name == "Guest" and value == constants.SIDEBAR_READ_AND_UNREAD:
                        raise Exception(_("Guest can't have this view"))
                    # check for valid value, last on checks for power of 2 value
                    if value > 0 and value <= constants.SIDEBAR_LIST and (value & value - 1 == 0 or value == 1):
                        if vals['value'] == 'true':
                            user.sidebar_view |= value
                        elif vals['value'] == 'false':
                            user.sidebar_view &= ~value
                        else:
                            raise Exception(_("Value has to be true or false"))
                    else:
                        raise Exception(_("Invalid view"))
                elif param == 'locale':
                    if user.name == "Guest":
                        raise Exception(_("Guest's Locale is determined automatically and can't be set"))
                    if vals['value'] in get_available_translations():
                        user.locale = vals['value']
                    else:
                        raise Exception(_("No Valid Locale Given"))
                elif param == 'default_language':
                    languages = calibre_db.session.query(db.Languages) \
                        .join(db.books_languages_link) \
                        .join(db.Books) \
                        .filter(calibre_db.common_filters()) \
                        .group_by(db.Languages.id).all()
                    lang_codes = [lang.lang_code for lang in languages] + ["all"]
                    if vals['value'] in lang_codes:
                        user.default_language = vals['value']
                    else:
                        raise Exception(_("No Valid Book Language Given"))
                else:
                    return _("Parameter not found"), 400
        except Exception as ex:
            log.error_or_exception(ex)
            return str(ex), 400
    ub.session_commit()
    return ""

@admi.route("/ajax/user_table_settings", methods=['POST'])
@user_login_required
@admin_required
def update_table_settings():
    current_user.view_settings['useredit'] = json.loads(request.data)
    try:
        try:
            flag_modified(current_user, "view_settings")
        except AttributeError:
            pass
        ub.session.commit()
    except (InvalidRequestError, OperationalError):
        log.error("Invalid request received: {}".format(request))
        return "Invalid request", 400
    return ""

@admi.route("/admin/viewconfig", methods=["POST"])
@user_login_required
@admin_required
def update_view_configuration():
    to_save = request.form.to_dict()

    _config_string(to_save, "config_calibre_web_title")
    _config_string(to_save, "config_columns_to_ignore")
    if _config_string(to_save, "config_title_regex"):
        calibre_db.update_title_sort(config)

    if not check_valid_read_column(to_save.get("config_read_column", "0")):
        flash(_("Invalid Read Column"), category="error")
        log.debug("Invalid Read column")
        return view_configuration()
    _config_int(to_save, "config_read_column")

    if not check_valid_restricted_column(to_save.get("config_restricted_column", "0")):
        flash(_("Invalid Restricted Column"), category="error")
        log.debug("Invalid Restricted Column")
        return view_configuration()
    _config_int(to_save, "config_restricted_column")

    _config_int(to_save, "config_theme")
    _config_int(to_save, "config_random_books")
    _config_int(to_save, "config_books_per_page")
    _config_int(to_save, "config_authors_max")
    _config_string(to_save, "config_default_language")
    _config_string(to_save, "config_default_locale")

    config.config_default_role = constants.selected_roles(to_save)
    config.config_default_role &= ~constants.ROLE_ANONYMOUS

    config.config_default_show = sum(int(k[5:]) for k in to_save if k.startswith('show_'))
    if "Show_detail_random" in to_save:
        config.config_default_show |= constants.DETAIL_RANDOM

    config.save()
    flash(_("Calibre-Web configuration updated"), category="success")
    log.debug("Calibre-Web configuration updated")
    before_request()

    return view_configuration()

@admi.route("/ajax/loaddialogtexts/<element_id>", methods=['POST'])
@user_login_required
def load_dialogtexts(element_id):
    texts = {"header": "", "main": "", "valid": 1}
    if element_id == "config_delete_kobo_token":
        texts["main"] = _('Do you really want to delete the Kobo Token?')
    elif element_id == "btndeletedomain":
        texts["main"] = _('Do you really want to delete this domain?')
    elif element_id == "btndeluser":
        texts["main"] = _('Do you really want to delete this user?')
    elif element_id == "delete_shelf":
        texts["main"] = _('Are you sure you want to delete this shelf?')
    elif element_id == "select_locale":
        texts["main"] = _('Are you sure you want to change locales of selected user(s)?')
    elif element_id == "select_default_language":
        texts["main"] = _('Are you sure you want to change visible book languages for selected user(s)?')
    elif element_id == "role":
        texts["main"] = _('Are you sure you want to change the selected role for the selected user(s)?')
    elif element_id == "restrictions":
        texts["main"] = _('Are you sure you want to change the selected restrictions for the selected user(s)?')
    elif element_id == "sidebar_view":
        texts["main"] = _('Are you sure you want to change the selected visibility restrictions '
                          'for the selected user(s)?')
    elif element_id == "kobo_only_shelves_sync":
        texts["main"] = _('Are you sure you want to change shelf sync behavior for the selected user(s)?')
    elif element_id == "db_submit":
        texts["main"] = _('Are you sure you want to change Calibre library location?')
    elif element_id == "admin_refresh_cover_cache":
        texts["main"] = _('Calibre-Web will search for updated Covers '
                          'and update Cover Thumbnails, this may take a while?')
    elif element_id == "btnfullsync":
        texts["main"] = _("Are you sure you want delete Calibre-Web's sync database "
                          "to force a full sync with your Kobo Reader?")
    return json.dumps(texts)

@admi.route("/ajax/editdomain/<int:allow>", methods=['POST'])
@user_login_required
@admin_required
def edit_domain(allow):
    vals = request.form.to_dict()
    answer = ub.session.query(ub.Registration).filter(ub.Registration.id == vals['pk']).first()
    answer.domain = vals['value'].replace('*', '%').replace('?', '_').lower()
    return ub.session_commit("Registering Domains edited {}".format(answer.domain))

@admi.route("/ajax/adddomain/<int:allow>", methods=['POST'])
@user_login_required
@admin_required
def add_domain(allow):
    domain_name = request.form.to_dict()['domainname'].replace('*', '%').replace('?', '_').lower()
    check = ub.session.query(ub.Registration).filter(ub.Registration.domain == domain_name) \
        .filter(ub.Registration.allow == allow).first()
    if not check:
        new_domain = ub.Registration(domain=domain_name, allow=allow)
        ub.session.add(new_domain)
        ub.session_commit("Registering Domains added {}".format(domain_name))
    return ""

@admi.route("/ajax/deletedomain", methods=['POST'])
@user_login_required
@admin_required
def delete_domain():
    try:
        domain_id = request.form.to_dict()['domainid'].replace('*', '%').replace('?', '_').lower()
        ub.session.query(ub.Registration).filter(ub.Registration.id == domain_id).delete()
        ub.session_commit("Registering Domains deleted {}".format(domain_id))
        # If last domain was deleted, add all domains by default
        if not ub.session.query(ub.Registration).filter(ub.Registration.allow == 1).count():
            new_domain = ub.Registration(domain="%.%", allow=1)
            ub.session.add(new_domain)
            ub.session_commit("Last Registering Domain deleted, added *.* as default")
    except KeyError:
        pass
    return ""

@admi.route("/ajax/domainlist/<int:allow>")
@user_login_required
@admin_required
def list_domain(allow):
    answer = ub.session.query(ub.Registration).filter(ub.Registration.allow == allow).all()
    json_dumps = json.dumps([{"domain": r.domain.replace('%', '*').replace('_', '?'), "id": r.id} for r in answer])
    js = json.dumps(json_dumps.replace('"', "'")).lstrip('"').strip('"')
    response = make_response(js.replace("'", '"'))
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response

@admi.route("/ajax/editrestriction/<int:res_type>", defaults={"user_id": 0}, methods=['POST'])
@admi.route("/ajax/editrestriction/<int:res_type>/<int:user_id>", methods=['POST'])
@user_login_required
@admin_required
def edit_restriction(res_type, user_id):
    element = request.form.to_dict()
    if element['id'].startswith('a'):
        if res_type == 0:  # Tags as template
            elementlist = config.list_allowed_tags()
            elementlist[int(element['id'][1:])] = element['Element']
            config.config_allowed_tags = ','.join(elementlist)
            config.save()
        if res_type == 1:  # CustomC
            elementlist = config.list_allowed_column_values()
            elementlist[int(element['id'][1:])] = element['Element']
            config.config_allowed_column_value = ','.join(elementlist)
            config.save()
        if res_type == 2:  # Tags per user
            if isinstance(user_id, int):
                usr = ub.session.query(ub.User).filter(ub.User.id == int(user_id)).first()
            else:
                usr = current_user
            elementlist = usr.list_allowed_tags()
            elementlist[int(element['id'][1:])] = element['Element']
            usr.allowed_tags = ','.join(elementlist)
            ub.session_commit("Changed allowed tags of user {} to {}".format(usr.name, usr.allowed_tags))
        if res_type == 3:  # CColumn per user
            if isinstance(user_id, int):
                usr = ub.session.query(ub.User).filter(ub.User.id == int(user_id)).first()
            else:
                usr = current_user
            elementlist = usr.list_allowed_column_values()
            elementlist[int(element['id'][1:])] = element['Element']
            usr.allowed_column_value = ','.join(elementlist)
            ub.session_commit("Changed allowed columns of user {} to {}".format(usr.name, usr.allowed_column_value))
    if element['id'].startswith('d'):
        if res_type == 0:  # Tags as template
            elementlist = config.list_denied_tags()
            elementlist[int(element['id'][1:])] = element['Element']
            config.config_denied_tags = ','.join(elementlist)
            config.save()
        if res_type == 1:  # CustomC
            elementlist = config.list_denied_column_values()
            elementlist[int(element['id'][1:])] = element['Element']
            config.config_denied_column_value = ','.join(elementlist)
            config.save()
        if res_type == 2:  # Tags per user
            if isinstance(user_id, int):
                usr = ub.session.query(ub.User).filter(ub.User.id == int(user_id)).first()
            else:
                usr = current_user
            elementlist = usr.list_denied_tags()
            elementlist[int(element['id'][1:])] = element['Element']
            usr.denied_tags = ','.join(elementlist)
            ub.session_commit("Changed denied tags of user {} to {}".format(usr.name, usr.denied_tags))
        if res_type == 3:  # CColumn per user
            if isinstance(user_id, int):
                usr = ub.session.query(ub.User).filter(ub.User.id == int(user_id)).first()
            else:
                usr = current_user
            elementlist = usr.list_denied_column_values()
            elementlist[int(element['id'][1:])] = element['Element']
            usr.denied_column_value = ','.join(elementlist)
            ub.session_commit("Changed denied columns of user {} to {}".format(usr.name, usr.denied_column_value))
    return ""

@admi.route("/ajax/addrestriction/<int:res_type>", methods=['POST'])
@user_login_required
@admin_required
def add_user_0_restriction(res_type):
    return add_restriction(res_type, 0)

@admi.route("/ajax/addrestriction/<int:res_type>/<int:user_id>", methods=['POST'])
@user_login_required
@admin_required
def add_restriction(res_type, user_id):
    element = request.form.to_dict()
    if res_type == 0:  # Tags as template
        if 'submit_allow' in element:
            config.config_allowed_tags = restriction_addition(element, config.list_allowed_tags)
            config.save()
        elif 'submit_deny' in element:
            config.config_denied_tags = restriction_addition(element, config.list_denied_tags)
            config.save()
    if res_type == 1:  # CCustom as template
        if 'submit_allow' in element:
            config.config_allowed_column_value = restriction_addition(element, config.list_denied_column_values)
            config.save()
        elif 'submit_deny' in element:
            config.config_denied_column_value = restriction_addition(element, config.list_allowed_column_values)
            config.save()
    if res_type == 2:  # Tags per user
        if isinstance(user_id, int):
            usr = ub.session.query(ub.User).filter(ub.User.id == int(user_id)).first()
        else:
            usr = current_user
        if 'submit_allow' in element:
            usr.allowed_tags = restriction_addition(element, usr.list_allowed_tags)
            ub.session_commit("Changed allowed tags of user {} to {}".format(usr.name, usr.list_allowed_tags()))
        elif 'submit_deny' in element:
            usr.denied_tags = restriction_addition(element, usr.list_denied_tags)
            ub.session_commit("Changed denied tags of user {} to {}".format(usr.name, usr.list_denied_tags()))
    if res_type == 3:  # CustomC per user
        if isinstance(user_id, int):
            usr = ub.session.query(ub.User).filter(ub.User.id == int(user_id)).first()
        else:
            usr = current_user
        if 'submit_allow' in element:
            usr.allowed_column_value = restriction_addition(element, usr.list_allowed_column_values)
            ub.session_commit("Changed allowed columns of user {} to {}".format(usr.name,
                                                                                usr.list_allowed_column_values()))
        elif 'submit_deny' in element:
            usr.denied_column_value = restriction_addition(element, usr.list_denied_column_values)
            ub.session_commit("Changed denied columns of user {} to {}".format(usr.name,
                                                                               usr.list_denied_column_values()))
    return ""

@admi.route("/ajax/deleterestriction/<int:res_type>", methods=['POST'])
@user_login_required
@admin_required
def delete_user_0_restriction(res_type):
    return delete_restriction(res_type, 0)

@admi.route("/ajax/deleterestriction/<int:res_type>/<int:user_id>", methods=['POST'])
@user_login_required
@admin_required
def delete_restriction(res_type, user_id):
    element = request.form.to_dict()
    if res_type == 0:  # Tags as template
        if element['id'].startswith('a'):
            config.config_allowed_tags = restriction_deletion(element, config.list_allowed_tags)
            config.save()
        elif element['id'].startswith('d'):
            config.config_denied_tags = restriction_deletion(element, config.list_denied_tags)
            config.save()
    elif res_type == 1:  # CustomC as template
        if element['id'].startswith('a'):
            config.config_allowed_column_value = restriction_deletion(element, config.list_allowed_column_values)
            config.save()
        elif element['id'].startswith('d'):
            config.config_denied_column_value = restriction_deletion(element, config.list_denied_column_values)
            config.save()
    elif res_type == 2:  # Tags per user
        if isinstance(user_id, int):
            usr = ub.session.query(ub.User).filter(ub.User.id == int(user_id)).first()
        else:
            usr = current_user
        if element['id'].startswith('a'):
            usr.allowed_tags = restriction_deletion(element, usr.list_allowed_tags)
            ub.session_commit("Deleted allowed tags of user {}: {}".format(usr.name, element['Element']))
        elif element['id'].startswith('d'):
            usr.denied_tags = restriction_deletion(element, usr.list_denied_tags)
            ub.session_commit("Deleted denied tag of user {}: {}".format(usr.name, element['Element']))
    elif res_type == 3:  # Columns per user
        if isinstance(user_id, int):
            usr = ub.session.query(ub.User).filter(ub.User.id == int(user_id)).first()
        else:
            usr = current_user
        if element['id'].startswith('a'):
            usr.allowed_column_value = restriction_deletion(element, usr.list_allowed_column_values)
            ub.session_commit("Deleted allowed columns of user {}: {}".format(usr.name,
                                                                              usr.list_allowed_column_values()))

        elif element['id'].startswith('d'):
            usr.denied_column_value = restriction_deletion(element, usr.list_denied_column_values)
            ub.session_commit("Deleted denied columns of user {}: {}".format(usr.name,
                                                                             usr.list_denied_column_values()))
    return ""

@admi.route("/ajax/listrestriction/<int:res_type>", defaults={"user_id": 0})
@admi.route("/ajax/listrestriction/<int:res_type>/<int:user_id>")
@user_login_required
@admin_required
def list_restriction(res_type, user_id):
    if res_type == 0:  # Tags as template
        restrict = [{'Element': x, 'type': _('Deny'), 'id': 'd' + str(i)}
                    for i, x in enumerate(config.list_denied_tags()) if x != '']
        allow = [{'Element': x, 'type': _('Allow'), 'id': 'a' + str(i)}
                 for i, x in enumerate(config.list_allowed_tags()) if x != '']
        json_dumps = restrict + allow
    elif res_type == 1:  # CustomC as template
        restrict = [{'Element': x, 'type': _('Deny'), 'id': 'd' + str(i)}
                    for i, x in enumerate(config.list_denied_column_values()) if x != '']
        allow = [{'Element': x, 'type': _('Allow'), 'id': 'a' + str(i)}
                 for i, x in enumerate(config.list_allowed_column_values()) if x != '']
        json_dumps = restrict + allow
    elif res_type == 2:  # Tags per user
        if isinstance(user_id, int):
            usr = ub.session.query(ub.User).filter(ub.User.id == user_id).first()
        else:
            usr = current_user
        restrict = [{'Element': x, 'type': _('Deny'), 'id': 'd' + str(i)}
                    for i, x in enumerate(usr.list_denied_tags()) if x != '']
        allow = [{'Element': x, 'type': _('Allow'), 'id': 'a' + str(i)}
                 for i, x in enumerate(usr.list_allowed_tags()) if x != '']
        json_dumps = restrict + allow
    elif res_type == 3:  # CustomC per user
        if isinstance(user_id, int):
            usr = ub.session.query(ub.User).filter(ub.User.id == user_id).first()
        else:
            usr = current_user
        restrict = [{'Element': x, 'type': _('Deny'), 'id': 'd' + str(i)}
                    for i, x in enumerate(usr.list_denied_column_values()) if x != '']
        allow = [{'Element': x, 'type': _('Allow'), 'id': 'a' + str(i)}
                 for i, x in enumerate(usr.list_allowed_column_values()) if x != '']
        json_dumps = restrict + allow
    else:
        json_dumps = ""
    js = json.dumps(json_dumps)
    response = make_response(js)
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response

@admi.route("/ajax/fullsync", methods=["POST"])
@user_login_required
def ajax_self_fullsync():
    return do_full_kobo_sync(current_user.id)

@admi.route("/ajax/fullsync/<int:userid>", methods=["POST"])
@user_login_required
@admin_required
def ajax_fullsync(userid):
    return do_full_kobo_sync(userid)

@admi.route("/ajax/pathchooser/")
@user_login_required
@admin_required
def ajax_pathchooser():
    return pathchooser()

def do_full_kobo_sync(userid):
    count = ub.session.query(ub.KoboSyncedBooks).filter(userid == ub.KoboSyncedBooks.user_id).delete()
    message = _("{} sync entries deleted").format(count)
    ub.session_commit(message)
    return Response(json.dumps([{"type": "success", "message": message}]), mimetype='application/json')

def check_valid_read_column(column):
    if column != "0":
        if not calibre_db.session.query(db.CustomColumns).filter(db.CustomColumns.id == column) \
          .filter(and_(db.CustomColumns.datatype == 'bool', db.CustomColumns.mark_for_delete == False)).all():
            return False
    return True

def check_valid_restricted_column(column):
    if column != "0":
        if not calibre_db.session.query(db.CustomColumns).filter(db.CustomColumns.id == column) \
          .filter(and_(db.CustomColumns.datatype == 'text', db.CustomColumns.mark_for_delete == False)).all():
            return False
    return True

def restriction_addition(element, list_func):
    elementlist = list_func()
    if elementlist == ['']:
        elementlist = []
    if not element['add_element'] in elementlist:
        elementlist += [element['add_element']]
    return ','.join(elementlist)

def restriction_deletion(element, list_func):
    elementlist = list_func()
    if element['Element'] in elementlist:
        elementlist.remove(element['Element'])
    return ','.join(elementlist)

def prepare_tags(user, action, tags_name, id_list):
    if "tags" in tags_name:
        tags = calibre_db.session.query(db.Tags).filter(db.Tags.id.in_(id_list)).all()
        if not tags:
            raise Exception(_("Tag not found"))
        new_tags_list = [x.name for x in tags]
    else:
        tags = calibre_db.session.query(db.cc_classes[config.config_restricted_column]) \
            .filter(db.cc_classes[config.config_restricted_column].id.in_(id_list)).all()
        new_tags_list = [x.value for x in tags]
    saved_tags_list = user.__dict__[tags_name].split(",") if len(user.__dict__[tags_name]) else []
    if action == "remove":
        saved_tags_list = [x for x in saved_tags_list if x not in new_tags_list]
    elif action == "add":
        saved_tags_list.extend(x for x in new_tags_list if x not in saved_tags_list)
    else:
        raise Exception(_("Invalid Action"))
    return ",".join(saved_tags_list)

def get_drives(current):
    drive_letters = []
    for d in string.ascii_uppercase:
        if os.path.exists('{}:'.format(d)) and current[0].lower() != d.lower():
            drive = "{}:\\".format(d)
            data = {"name": drive, "fullpath": drive, "type": "dir", "size": "", "sort": "_" + drive.lower()}
            drive_letters.append(data)
    return drive_letters

def pathchooser():
    browse_for = "folder"
    folder_only = request.args.get('folder', False) == "true"
    file_filter = request.args.get('filter', "")
    path = os.path.normpath(request.args.get('path', ""))

    if os.path.isfile(path):
        old_file = path
        path = os.path.dirname(path)
    else:
        old_file = ""

    absolute = False

    if os.path.isdir(path):
        cwd = os.path.realpath(path)
        absolute = True
    else:
        cwd = os.getcwd()

    cwd = os.path.normpath(os.path.realpath(cwd))
    parent_dir = os.path.dirname(cwd)
    if not absolute:
        if os.path.realpath(cwd) == os.path.realpath("/"):
            cwd = os.path.relpath(cwd)
        else:
            cwd = os.path.relpath(cwd) + os.path.sep
        parent_dir = os.path.relpath(parent_dir) + os.path.sep

    files = []
    if os.path.realpath(cwd) == os.path.realpath("/") \
            or (sys.platform == "win32" and os.path.realpath(cwd)[1:] == os.path.realpath("/")[1:]):
        # we are in root
        parent_dir = ""
        if sys.platform == "win32":
            files = get_drives(cwd)

    try:
        folders = os.listdir(cwd)
    except Exception:
        folders = []

    for f in folders:
        try:
            sanitized_f = str(Markup.escape(f))
            data = {"name": sanitized_f, "fullpath": os.path.join(cwd, sanitized_f)}
            data["sort"] = data["fullpath"].lower()
        except Exception:
            continue

        if os.path.isfile(os.path.join(cwd, f)):
            if folder_only:
                continue
            if file_filter != "" and file_filter != f:
                continue
            data["type"] = "file"
            data["size"] = os.path.getsize(os.path.join(cwd, f))

            power = 0
            while (data["size"] >> 10) > 0.3:
                power += 1
                data["size"] >>= 10
            units = ("", "K", "M", "G", "T")
            data["size"] = str(data["size"]) + " " + units[power] + "Byte"
        else:
            data["type"] = "dir"
            data["size"] = ""

        files.append(data)

    files = sorted(files, key=operator.itemgetter("type", "sort"))

    context = {
        "cwd": cwd,
        "files": files,
        "parentdir": parent_dir,
        "type": browse_for,
        "oldfile": old_file,
        "absolute": absolute,
    }
    return json.dumps(context)

def _config_int(to_save, x, func=int):
    return config.set_from_dictionary(to_save, x, func)

def _config_checkbox(to_save, x):
    # Explicitly handle unchecked checkboxes (not present in form data)
    if x not in to_save:
        # Checkbox is unchecked, set to False
        if hasattr(config, x):
            setattr(config, x, False)
            return True
        return False
    return config.set_from_dictionary(to_save, x, lambda y: y == "on", False)

def _config_checkbox_int(to_save, x):
    # Explicitly handle unchecked checkboxes (not present in form data)
    if x not in to_save:
        # Checkbox is unchecked, set to 0
        if hasattr(config, x):
            setattr(config, x, 0)
            return True
        return False
    return config.set_from_dictionary(to_save, x, lambda y: 1 if (y == "on") else 0, 0)

def _config_string(to_save, x):
    return config.set_from_dictionary(to_save, x, lambda y: y.strip().strip(u'\u200B\u200C\u200D\ufeff') if y else y)

def _configuration_gdrive_helper(to_save):
    gdrive_error = None
    if to_save.get("config_use_google_drive"):
        gdrive_secrets = {}

        if not os.path.isfile(gdriveutils.SETTINGS_YAML):
            config.config_use_google_drive = False

        if gdrive_support:
            gdrive_error = gdriveutils.get_error_text(gdrive_secrets)
        if "config_use_google_drive" in to_save and not config.config_use_google_drive and not gdrive_error:
            with open(gdriveutils.CLIENT_SECRETS, 'r') as settings:
                gdrive_secrets = json.load(settings)['web']
            if not gdrive_secrets:
                return _configuration_result(_('client_secrets.json Is Not Configured For Web Application'))
            gdriveutils.update_settings(
                gdrive_secrets['client_id'],
                gdrive_secrets['client_secret'],
                gdrive_secrets['redirect_uris'][0]
            )

    # always show Google Drive settings, but in case of error deny support
    new_gdrive_value = (not gdrive_error) and ("config_use_google_drive" in to_save)
    if config.config_use_google_drive and not new_gdrive_value:
        config.config_google_drive_watch_changes_response = {}
    config.config_use_google_drive = new_gdrive_value
    if _config_string(to_save, "config_google_drive_folder"):
        gdriveutils.deleteDatabaseOnChange()
    return gdrive_error

# Update the OAuth configuration helper
def _configuration_oauth_helper(to_save):
    reboot_required = False
    for element in oauthblueprints:
        client_id_key = "config_" + str(element['id']) + "_oauth_client_id"
        client_secret_key = "config_" + str(element['id']) + "_oauth_client_secret"
        
        if client_id_key in to_save and client_secret_key in to_save:
            if (to_save[client_id_key] != element['oauth_client_id'] or 
                to_save[client_secret_key] != element['oauth_client_secret']):
                reboot_required = True
            
            # Update the provider in database
            ub.session.query(ub.OAuthProvider).filter(ub.OAuthProvider.id == element['id']).update(
                {"oauth_client_id": to_save[client_id_key],
                 "oauth_client_secret": to_save[client_secret_key],
                 "active": bool(to_save[client_id_key] and to_save[client_secret_key])})
    
    ub.session_commit("OAuth configuration updated")
    
    # Re-register OAuth clients with new credentials
    from .oauth_bb import generate_oauth_blueprints
    generate_oauth_blueprints()
    
    return reboot_required

def _configuration_logfile_helper(to_save):
    reboot_required = False
    reboot_required |= _config_int(to_save, "config_log_level")
    reboot_required |= _config_string(to_save, "config_logfile")
    if not logger.is_valid_logfile(config.config_logfile):
        return reboot_required, \
               _configuration_result(_('Logfile Location is not Valid, Please Enter Correct Path'))

    reboot_required |= _config_checkbox_int(to_save, "config_access_log")
    reboot_required |= _config_string(to_save, "config_access_logfile")
    if not logger.is_valid_logfile(config.config_access_logfile):
        return reboot_required, \
               _configuration_result(_('Access Logfile Location is not Valid, Please Enter Correct Path'))
    return reboot_required, None

def _configuration_ldap_helper(to_save):
    reboot_required = False
    reboot_required |= _config_int(to_save, "config_ldap_port")
    reboot_required |= _config_int(to_save, "config_ldap_authentication")
    reboot_required |= _config_string(to_save, "config_ldap_dn")
    reboot_required |= _config_string(to_save, "config_ldap_serv_username")
    reboot_required |= _config_string(to_save, "config_ldap_user_object")
    reboot_required |= _config_string(to_save, "config_ldap_group_object_filter")
    reboot_required |= _config_string(to_save, "config_ldap_group_members_field")
    reboot_required |= _config_string(to_save, "config_ldap_member_user_object")
    reboot_required |= _config_checkbox(to_save, "config_ldap_openldap")
    reboot_required |= _config_int(to_save, "config_ldap_encryption")
    reboot_required |= _config_string(to_save, "config_ldap_cacert_path")
    reboot_required |= _config_string(to_save, "config_ldap_cert_path")
    reboot_required |= _config_string(to_save, "config_ldap_key_path")
    _config_string(to_save, "config_ldap_group_name")

    address = urlparse(to_save.get("config_ldap_provider_url", ""))
    to_save["config_ldap_provider_url"] = (address.hostname or address.path).strip("/")
    reboot_required |= _config_string(to_save, "config_ldap_provider_url")

    if to_save.get("config_ldap_serv_password_e", "") != "":
        reboot_required |= 1
        config.set_from_dictionary(to_save, "config_ldap_serv_password_e")
    config.save()

    if not config.config_ldap_provider_url \
      or not config.config_ldap_port \
      or not config.config_ldap_dn \
      or not config.config_ldap_user_object:
        return reboot_required, _configuration_result(_('Please Enter a LDAP Provider, '
                                                        'Port, DN and User Object Identifier'))

    if config.config_ldap_authentication > constants.LDAP_AUTH_ANONYMOUS:
        if config.config_ldap_authentication > constants.LDAP_AUTH_UNAUTHENTICATE:
            if not config.config_ldap_serv_username or not bool(config.config_ldap_serv_password_e):
                return reboot_required, _configuration_result(_('Please Enter a LDAP Service Account and Password'))
        else:
            if not config.config_ldap_serv_username:
                return reboot_required, _configuration_result(_('Please Enter a LDAP Service Account'))

    if config.config_ldap_group_object_filter:
        if config.config_ldap_group_object_filter.count("%s") != 1:
            return reboot_required, \
                   _configuration_result(_('LDAP Group Object Filter Needs to Have One "%s" Format Identifier'))
        if config.config_ldap_group_object_filter.count("(") != config.config_ldap_group_object_filter.count(")"):
            return reboot_required, _configuration_result(_('LDAP Group Object Filter Has Unmatched Parenthesis'))

    if config.config_ldap_user_object.count("%s") != 1:
        return reboot_required, \
               _configuration_result(_('LDAP User Object Filter needs to Have One "%s" Format Identifier'))
    if config.config_ldap_user_object.count("(") != config.config_ldap_user_object.count(")"):
        return reboot_required, _configuration_result(_('LDAP User Object Filter Has Unmatched Parenthesis'))

    if to_save.get("ldap_import_user_filter") == '0':
        config.config_ldap_member_user_object = ""
    else:
        if config.config_ldap_member_user_object.count("%s") != 1:
            return reboot_required, \
                   _configuration_result(_('LDAP Member User Filter needs to Have One "%s" Format Identifier'))
        if config.config_ldap_member_user_object.count("(") != config.config_ldap_member_user_object.count(")"):
            return reboot_required, _configuration_result(_('LDAP Member User Filter Has Unmatched Parenthesis'))

    if config.config_ldap_cacert_path or config.config_ldap_cert_path or config.config_ldap_key_path:
        if not (os.path.isfile(config.config_ldap_cacert_path) and
                os.path.isfile(config.config_ldap_cert_path) and
                os.path.isfile(config.config_ldap_key_path)):
            return reboot_required, \
                   _configuration_result(_('LDAP CACertificate, Certificate or Key Location is not Valid, '
                                           'Please Enter Correct Path'))
    return reboot_required, None

@admi.route("/ajax/simulatedbchange", methods=['POST'])
@user_login_required
@admin_required
def simulatedbchange():
    db_change, db_valid = _db_simulate_change()
    return Response(json.dumps({"change": db_change, "valid": db_valid}), mimetype='application/json')

@admi.route("/admin/user/new", methods=["GET", "POST"])
@user_login_required
@admin_required
def new_user():
    content = ub.User()
    languages = calibre_db.speaking_language()
    translations = get_available_locale()
    kobo_support = feature_support['kobo'] and config.config_kobo_sync
    if request.method == "POST":
        to_save = request.form.to_dict()
        _handle_new_user(to_save, content, languages, translations, kobo_support)
    else:
        content.role = config.config_default_role
        content.sidebar_view = config.config_default_show
        content.locale = config.config_default_locale
        content.default_language = config.config_default_language
    return render_title_template("user_edit.html", new_user=1, content=content,
                                 config=config, translations=translations,
                                 languages=languages, title=_("Add New User"), page="newuser",
                                 kobo_support=kobo_support, registered_oauth=oauth_check)

@admi.route("/admin/mailsettings", methods=["GET"])
@user_login_required
@admin_required
def edit_mailsettings():
    content = config.get_mail_settings()
    return render_title_template("email_edit.html", content=content, title=_("Edit Email Server Settings"),
                                 page="mailset", feature_support=feature_support)

@admi.route("/admin/mailsettings", methods=["POST"])
@user_login_required
@admin_required
def update_mailsettings():
    to_save = request.form.to_dict()
    log.info("Updating Mail Settings with data: {}".format(to_save))
    _config_int(to_save, "mail_server_type")
    if to_save.get("invalidate"):
        config.mail_gmail_token = {}
        try:
            flag_modified(config, "mail_gmail_token")
        except AttributeError:
            pass
    elif to_save.get("gmail"):
        try:
            config.mail_gmail_token = services.gmail.setup_gmail(config.mail_gmail_token)
            flash(_("Success! Gmail Account Verified."), category="success")
        except Exception as ex:
            flash(str(ex), category="error")
            log.error(ex)
            return edit_mailsettings()

    else:
        _config_int(to_save, "mail_port")
        _config_int(to_save, "mail_use_ssl")
        
        # DEBUG: Log password saving attempt (masked)
        if to_save.get("mail_password_e"):
             log.info("Updating Mail Settings: Password provided in form, updating configuration.")
        else:
             log.info("Updating Mail Settings: No password in form, keeping existing password.")

        if to_save.get("mail_password_e", ""):
            _config_string(to_save, "mail_password_e")
        _config_int(to_save, "mail_size", lambda y: int(y) * 1024 * 1024)
        _config_string(to_save, "mail_server")
        _config_string(to_save, "mail_from")
        _config_string(to_save, "mail_login")
    try:
        config.save()
        # Explicitly reload config to ensure we have the latest data
        config.load()
        log.info("Mail settings saved successfully")
    except (OperationalError, InvalidRequestError) as e:
        ub.session.rollback()
        log.error_or_exception("Settings Database error: {}".format(e))
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        flash(_("Oops! Database Error: %(error)s.", error=error_msg), category="error")
        return edit_mailsettings()
    except Exception as e:
        log.error_or_exception("Unexpected error saving mail settings: {}".format(e))
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        flash(_("Oops! Database Error: %(error)s.", error=error_msg), category="error")
        return edit_mailsettings()

    if to_save.get("test"):
        if current_user.email:
            result = send_test_mail(current_user.email, current_user.name)
            if result is None:
                flash(_("Test e-mail queued for sending to %(email)s, please check Tasks for result",
                        email=current_user.email), category="info")
            else:
                flash(_("There was an error sending the Test e-mail: %(res)s", res=result), category="error")
        else:
            flash(_("Please configure your e-mail address first..."), category="error")
    else:
        flash(_("Email Server Settings updated"), category="success")

    return edit_mailsettings()

@admi.route("/admin/scheduledtasks")
@user_login_required
@admin_required
def edit_scheduledtasks():
    content = config.get_scheduled_task_settings()
    time_field = list()
    duration_field = list()

    for n in range(24):
        time_field.append((n, format_time(datetime_time(hour=n), format="short", )))
    for n in range(5, 65, 5):
        t = timedelta(hours=n // 60, minutes=n % 60)
        duration_field.append((n, format_timedelta(t, threshold=.97)))

    return render_title_template("schedule_edit.html",
                                 config=content,
                                 starttime=time_field,
                                 duration=duration_field,
                                 title=_("Edit Scheduled Tasks Settings"))

@admi.route("/admin/scheduledtasks", methods=["POST"])
@user_login_required
@admin_required
def update_scheduledtasks():
    error = False
    to_save = request.form.to_dict()
    if 0 <= int(to_save.get("schedule_start_time")) <= 23:
        _config_int(to_save, "schedule_start_time")
    else:
        flash(_("Invalid start time for task specified"), category="error")
        error = True
    if 0 < int(to_save.get("schedule_duration")) <= 60:
        _config_int(to_save, "schedule_duration")
    else:
        flash(_("Invalid duration for task specified"), category="error")
        error = True
    _config_checkbox(to_save, "schedule_generate_book_covers")
    _config_checkbox(to_save, "schedule_generate_series_covers")
    _config_checkbox(to_save, "schedule_metadata_backup")
    _config_checkbox(to_save, "schedule_reconnect")

    if not error:
        try:
            config.save()
            flash(_("Scheduled tasks settings updated"), category="success")

            # Cancel any running tasks
            schedule.end_scheduled_tasks()

            # Re-register tasks with new settings
            schedule.register_scheduled_tasks(config.schedule_reconnect)
        except IntegrityError:
            ub.session.rollback()
            log.error("An unknown error occurred while saving scheduled tasks settings")
            flash(_("Oops! An unknown error occurred. Please try again later."), category="error")
        except OperationalError:
            ub.session.rollback()
            log.error("Settings DB is not Writeable")
            flash(_("Settings DB is not Writeable"), category="error")

    return edit_scheduledtasks()

@admi.route("/admin/user/<int:user_id>", methods=["GET", "POST"])
@user_login_required
@admin_required
def edit_user(user_id):
    content = ub.session.query(ub.User).filter(ub.User.id == int(user_id)).first()  # type: ub.User
    if not content or (not config.config_anonbrowse and content.name == "Guest"):
        flash(_("User not found"), category="error")
        return redirect(url_for('admin.admin'))
    languages = calibre_db.speaking_language(return_all_languages=True)
    translations = get_available_locale()
    kobo_support = feature_support['kobo'] and config.config_kobo_sync
    if request.method == "POST":
        to_save = request.form.to_dict()
        resp = _handle_edit_user(to_save, content, languages, translations, kobo_support)
        if resp:
            return resp
    return render_title_template("user_edit.html",
                                 translations=translations,
                                 languages=languages,
                                 new_user=0,
                                 content=content,
                                 config=config,
                                 registered_oauth=oauth_check,
                                 mail_configured=config.get_mail_server_configured(),
                                 kobo_support=kobo_support,
                                 title=_("Edit User %(nick)s", nick=content.name),
                                 page="edituser")

@admi.route("/admin/resetpassword/<int:user_id>", methods=["POST"])
@user_login_required
@admin_required
def reset_user_password(user_id):
    if current_user is not None and current_user.is_authenticated:
        ret, message = reset_password(user_id)
        if ret == 1:
            log.debug("Password for user %s reset", message)
            flash(_("Success! Password for user %(user)s reset", user=message), category="success")
        elif ret == 0:
            log.error("An unknown error occurred. Please try again later.")
            flash(_("Oops! An unknown error occurred. Please try again later."), category="error")
        else:
            log.error("Please configure the SMTP mail settings.")
            flash(_("Oops! Please configure the SMTP mail settings."), category="error")
    return redirect(url_for('admin.admin'))

@admi.route("/admin/logfile")
@user_login_required
@admin_required
def view_logfile():
    logfiles = {0: logger.get_logfile(config.config_logfile),
                1: logger.get_accesslogfile(config.config_access_logfile)}
    return render_title_template("logviewer.html",
                                 title=_("Logfile viewer"),
                                 accesslog_enable=config.config_access_log,
                                 log_enable=bool(config.config_logfile != logger.LOG_TO_STDOUT),
                                 logfiles=logfiles,
                                 page="logfile")

@admi.route("/ajax/log/<int:logtype>")
@user_login_required
@admin_required
def send_logfile(logtype):
    if logtype == 1:
        logfile = logger.get_accesslogfile(config.config_access_logfile)
        return send_from_directory(os.path.dirname(logfile),
                                   os.path.basename(logfile))
    if logtype == 0:
        logfile = logger.get_logfile(config.config_logfile)
        return send_from_directory(os.path.dirname(logfile),
                                   os.path.basename(logfile))
    else:
        return ""

@admi.route("/admin/logdownload/<int:logtype>")
@user_login_required
@admin_required
def download_log(logtype):
    if logtype == 0:
        file_name = logger.get_logfile(config.config_logfile)
    elif logtype == 1:
        file_name = logger.get_accesslogfile(config.config_access_logfile)
    else:
        abort(404)
    if logger.is_valid_logfile(file_name):
        return debug_info.assemble_logfiles(file_name)
    abort(404)

@admi.route("/admin/debug")
@user_login_required
@admin_required
def download_debug():
    return debug_info.send_debug()

@admi.route("/get_update_status", methods=['GET'])
@user_login_required
@admin_required
def get_update_status():
    if feature_support['updater']:
        log.info("Update status requested")
        return updater_thread.get_available_updates(request.method)
    else:
        return ''

@admi.route("/get_updater_status", methods=['GET', 'POST'])
@user_login_required
@admin_required
def get_updater_status():
    status = {}
    if feature_support['updater']:
        if request.method == "POST":
            commit = request.form.to_dict()
            if "start" in commit and commit['start'] == 'True':
                txt = {
                    "1": _(u'Requesting update package'),
                    "2": _(u'Downloading update package'),
                    "3": _(u'Unzipping update package'),
                    "4": _(u'Replacing files'),
                    "5": _(u'Database connections are closed'),
                    "6": _(u'Stopping server'),
                    "7": _(u'Update finished, please press okay and reload page'),
                    "8": _(u'Update failed:') + u' ' + _(u'HTTP Error'),
                    "9": _(u'Update failed:') + u' ' + _(u'Connection error'),
                    "10": _(u'Update failed:') + u' ' + _(u'Timeout while establishing connection'),
                    "11": _(u'Update failed:') + u' ' + _(u'General error'),
                    "12": _(u'Update failed:') + u' ' + _(u'Update file could not be saved in temp dir'),
                    "13": _(u'Update failed:') + u' ' + _(u'Files could not be replaced during update')
                }
                status['text'] = txt
                updater_thread.status = 0
                updater_thread.resume()
                status['status'] = updater_thread.get_update_status()
        elif request.method == "GET":
            try:
                status['status'] = updater_thread.get_update_status()
                if status['status'] == -1:
                    status['status'] = 7
            except Exception:
                status['status'] = 11
        return json.dumps(status)
    return ''

def ldap_import_create_user(user, user_data):
    user_login_field = extract_dynamic_field_from_filter(user, config.config_ldap_user_object)

    try:
        username = user_data[user_login_field][0].decode('utf-8')
    except KeyError as ex:
        log.error("Failed to extract LDAP user: %s - %s", user, ex)
        message = _(u'Failed to extract at least One LDAP User')
        return 0, message

    # check for duplicate username
    if ub.session.query(ub.User).filter(func.lower(ub.User.name) == username.lower()).first():
        log.warning("LDAP User  %s Already in Database", user_data)
        return 0, None

    ereader_mail = ''
    if 'mail' in user_data:
        useremail = user_data['mail'][0].decode('utf-8')
        if len(user_data['mail']) > 1:
            ereader_mail = user_data['mail'][1].decode('utf-8')
    else:
        log.debug('No Mail Field Found in LDAP Response')
        useremail = username + '@email.com'

    try:
        # check for duplicate email
        useremail = check_email(useremail)
    except Exception as ex:
        log.warning("LDAP Email Error: {}, {}".format(user_data, ex))
        return 0, None
    content = ub.User()
    content.name = username
    content.password = ''  # dummy password which will be replaced by ldap one
    content.email = useremail
    content.kindle_mail = ereader_mail
    content.default_language = config.config_default_language
    content.locale = config.config_default_locale
    content.role = config.config_default_role
    content.sidebar_view = config.config_default_show
    content.allowed_tags = config.config_allowed_tags
    content.denied_tags = config.config_denied_tags
    content.allowed_column_value = config.config_allowed_column_value
    content.denied_column_value = config.config_denied_column_value
    ub.session.add(content)
    try:
        ub.session.commit()
        return 1, None  # increase no of users
    except Exception as ex:
        log.warning("Failed to create LDAP user: %s - %s", user, ex)
        ub.session.rollback()
        message = _(u'Failed to Create at Least One LDAP User')
        return 0, message

@admi.route('/import_ldap_users', methods=["POST"])
@user_login_required
@admin_required
def import_ldap_users():
    showtext = {}
    try:
        new_users = services.ldap.get_group_members(config.config_ldap_group_name)
    except (services.ldap.LDAPException, TypeError, AttributeError, KeyError) as e:
        log.error_or_exception(e)
        showtext['text'] = _(u'Error: %(ldaperror)s', ldaperror=e)
        return json.dumps(showtext)
    if not new_users:
        log.debug('LDAP empty response')
        showtext['text'] = _(u'Error: No user returned in response of LDAP server')
        return json.dumps(showtext)

    imported = 0
    for username in new_users:
        if isinstance(username, bytes):
            user = username.decode('utf-8')
        else:
            user = username
        if '=' in user:
            # if member object field is empty take user object as filter
            if config.config_ldap_member_user_object:
                query_filter = config.config_ldap_member_user_object
            else:
                query_filter = config.config_ldap_user_object
            try:
                user_identifier = extract_user_identifier(user, query_filter)
            except Exception as ex:
                log.warning(ex)
                continue
        else:
            user_identifier = user
            query_filter = None
        try:
            user_data = services.ldap.get_object_details(user=user_identifier, query_filter=query_filter)
        except AttributeError as ex:
            log.error_or_exception(ex)
            continue
        if user_data:
            user_count, message = ldap_import_create_user(user, user_data)
            if message:
                showtext['text'] = message
            else:
                imported += user_count
        else:
            log.warning("LDAP User: %s Not Found", user)
            showtext['text'] = _(u'At Least One LDAP User Not Found in Database')
    if not showtext:
        showtext['text'] = _(u'{} User Successfully Imported'.format(imported))
    return json.dumps(showtext)

@admi.route("/ajax/canceltask", methods=['POST'])
@user_login_required
@admin_required
def cancel_task():
    task_id = request.get_json().get('task_id', None)
    worker = WorkerThread.get_instance()
    worker.end_task(task_id)
    return ""

def _db_simulate_change():
    param = request.form.to_dict()
    to_save = dict()
    # For PostgreSQL, we don't use file paths for database configuration
    # The config_calibre_dir parameter is kept for compatibility but not used for PostgreSQL connections
    to_save['config_calibre_dir'] = param.get('config_calibre_dir', '').strip()
    
    # For PostgreSQL, database validation is done via connection testing
    # rather than file existence checks
    db_valid = calibre_db.check_valid_db(to_save["config_calibre_dir"],
                                        ub.app_DB_path,
                                        config.config_calibre_uuid)
    
    log.info(f"PostgreSQL database validation: {db_valid}")
    
    # For PostgreSQL, we always consider the database as changed since we're using connection-based validation
    db_change = True
    
    return db_change, db_valid

# def _db_configuration_update_helper():
#     db_change = False
#     to_save = request.form.to_dict()
#     gdrive_error = None
#     log.info(f"Database configuration update request: {to_save}")

#     # For PostgreSQL, database configuration is handled via environment variables
#     # The config_calibre_dir parameter is kept for compatibility
#     to_save['config_calibre_dir'] = to_save.get('config_calibre_dir', '').strip()
    
#     db_valid = False
#     try:
#         # For PostgreSQL, database validation is connection-based
#         db_change, db_valid = _db_simulate_change()

#         # Google Drive setup
#         gdrive_error = _configuration_gdrive_helper(to_save)
#     except (OperationalError, InvalidRequestError) as e:
#         ub.session.rollback()
#         log.error_or_exception("Settings Database error: {}".format(e))
#         _db_configuration_result(_("Oops! Database Error: %(error)s.", error=e.orig), gdrive_error)
    
#     # For PostgreSQL, we always attempt to setup the database connection
#     # since we're using environment variables for configuration
#     if not db_valid or not config.db_configured:
#         log.info("Setting up PostgreSQL database connection")
#         calibre_db.setup_db(to_save['config_calibre_dir'], ub.app_DB_path)
        
#     config.store_calibre_uuid(calibre_db, db.Library_Id)
    
#     # If database changed -> delete shelfs, delete download books, delete read books, kobo sync...
#     if db_change:
#         log.info("Calibre Database changed, all Calibre-Web info related to old Database gets deleted")
#         ub.session.query(ub.Downloads).delete()
#         ub.session.query(ub.ArchivedBook).delete()
#         ub.session.query(ub.ReadBook).delete()
#         ub.session.query(ub.BookShelf).delete()
#         ub.session.query(ub.Bookmark).delete()
#         ub.session.query(ub.KoboReadingState).delete()
#         ub.session.query(ub.KoboStatistics).delete()
#         ub.session.query(ub.KoboSyncedBooks).delete()
#         helper.delete_thumbnail_cache()
#         ub.session_commit()
    
#     _config_string(to_save, "config_calibre_dir")
#     calibre_db.update_config(config)
    
#     _config_string(to_save, "config_calibre_split_dir")
#     config.config_calibre_split = to_save.get('config_calibre_split', 0) == "on"
#     calibre_db.update_config(config)
#     config.save()
#     return _db_configuration_result(None, gdrive_error)

def _db_configuration_update_helper():
    db_change = False
    to_save = request.form.to_dict()
    gdrive_error = None

    # Clean up the calibre directory path
    to_save['config_calibre_dir'] = re.sub(r'[\\/]metadata\.db$',
                                           '',
                                           to_save['config_calibre_dir'],
                                           flags=re.IGNORECASE)
    
    db_valid = False
    try:
        db_change, db_valid = _db_simulate_change()
        gdrive_error = _configuration_gdrive_helper(to_save)
    except (OperationalError, InvalidRequestError) as e:
        ub.session.rollback()
        log.error_or_exception("Settings Database error: {}".format(e))
        return _db_configuration_result(_("Oops! Database Error: %(error)s.", error=e.orig), gdrive_error)
    
    # Handle PostgreSQL migration for metadata if requested
    migrate_to_postgres = to_save.get('migrate_to_postgresql') == 'on'
    if config.config_use_postgresql and migrate_to_postgres:
        try:
            metadata_db_path = os.path.join(to_save['config_calibre_dir'], "metadata.db")
            if not os.path.exists(metadata_db_path):
                return _db_configuration_result(_('Metadata.db file not found at the specified location'), gdrive_error)
            
            postgres_url = get_postgres_metadata_url(config)
            migrate_metadata_to_postgres(metadata_db_path, postgres_url)
            flash(_("Metadata database migrated to PostgreSQL successfully"), category="success")
            
            # After migration, update the configuration to use PostgreSQL for metadata
            config.config_use_postgresql_metadata = True
            config.config_postgresql_metadata_url = postgres_url
            
        except Exception as e:
            log.error(f"PostgreSQL migration failed: {e}")
            return _db_configuration_result(_('PostgreSQL migration failed: %(error)s', error=str(e)), gdrive_error)

    # Handle Google Drive metadata.db download if needed
    try:
        metadata_db = os.path.join(to_save['config_calibre_dir'], "metadata.db")
        if config.config_use_google_drive and is_gdrive_ready() and not os.path.exists(metadata_db):
            gdriveutils.downloadFile(None, "metadata.db", metadata_db)
            db_change = True
    except Exception as ex:
        log.error(f"Google Drive download failed: {ex}")
        return _db_configuration_result('{}'.format(ex), gdrive_error)
    
    # Handle split directory configuration
    config.config_calibre_split = to_save.get('config_calibre_split', 'off') == "on"
    if config.config_calibre_split:
        split_dir = to_save.get("config_calibre_split_dir", "").strip()
        if not split_dir or not os.path.exists(split_dir):
            return _db_configuration_result(_("Books path is not valid or does not exist"), gdrive_error)
        else:
            _config_string(to_save, "config_calibre_split_dir")
    
    # Check if database configuration needs to be updated
    metadata_db_path = os.path.join(to_save['config_calibre_dir'], "metadata.db")
    needs_db_update = (db_change or 
                      not db_valid or 
                      not config.db_configured or 
                      config.config_calibre_dir != to_save["config_calibre_dir"])
    
    if needs_db_update:
        # Validate database location
        if not to_save['config_calibre_dir'] or not os.path.exists(metadata_db_path):
            return _db_configuration_result(_('Database location is not valid. Please enter correct path'), gdrive_error)
        
        # Setup database connection (PostgreSQL or SQLite)
        if config.config_use_postgresql and config.config_use_postgresql_metadata:
            # Use PostgreSQL for metadata
            calibre_db.setup_db(None, ub.app_DB_path, use_postgresql=True)
        else:
            # Use SQLite for metadata (original behavior)
            calibre_db.setup_db(to_save['config_calibre_dir'], ub.app_DB_path)
        
        # If database changed, perform cleanup operations
        if db_change:
            log.info("Calibre Database changed, cleaning up Calibre-Web related data")
            
            # Delete user data related to old database
            try:
                ub.session.query(ub.Downloads).delete()
                ub.session.query(ub.ArchivedBook).delete()
                ub.session.query(ub.ReadBook).delete()
                ub.session.query(ub.BookShelf).delete()
                ub.session.query(ub.Bookmark).delete()
                ub.session.query(ub.KoboReadingState).delete()
                ub.session.query(ub.KoboStatistics).delete()
                ub.session.query(ub.KoboSyncedBooks).delete()
                
                # Clear thumbnail cache
                helper.delete_thumbnail_cache()
                
                # Reset visibility settings
                config.config_restricted_column = 0
                config.config_denied_tags = ""
                config.config_allowed_tags = ""
                config.config_columns_to_ignore = ""
                config.config_denied_column_value = ""
                config.config_allowed_column_value = ""
                config.config_read_column = 0
                
                ub.session_commit()
                log.info("Database cleanup completed successfully")
                
            except Exception as cleanup_error:
                log.error(f"Database cleanup failed: {cleanup_error}")
                ub.session.rollback()
                return _db_configuration_result(_('Database cleanup failed'), gdrive_error)
        
        # Update configuration with new database path
        _config_string(to_save, "config_calibre_dir")
        
        # Update calibre database configuration
        calibre_db.update_config(config, config.config_calibre_dir, ub.app_DB_path)
        
        # Store Calibre UUID
        try:
            config.store_calibre_uuid(calibre_db, db.Library_Id)
        except Exception as uuid_error:
            log.warning(f"Could not store Calibre UUID: {uuid_error}")
        
        # Check write permissions for SQLite database
        if (not config.config_use_postgresql and 
            not config.config_use_postgresql_metadata and 
            not os.access(metadata_db_path, os.W_OK)):
            flash(_("Database is not writeable"), category="warning")
    
    # Final configuration updates
    calibre_db.update_config(config, config.config_calibre_dir, ub.app_DB_path)
    
    # Save configuration
    try:
        config.save()
        log.info("Database configuration saved successfully")
    except Exception as save_error:
        log.error(f"Failed to save configuration: {save_error}")
        return _db_configuration_result(_('Failed to save configuration'), gdrive_error)
    
    return _db_configuration_result(None, gdrive_error)


# Helper function for PostgreSQL metadata URL
def get_postgres_metadata_url(config):
    """Get PostgreSQL URL for metadata database"""
    if config.config_database_url:
        # Use the same database but different schema or same database
        base_url = config.config_database_url
        return base_url
    else:
        password = config.config_db_password or ''
        escaped_password = urllib.parse.quote_plus(password)
        return f"postgresql+psycopg2://{config.config_db_user}:{escaped_password}@{config.config_db_host}:{config.config_db_port}/{config.config_db_name}"


# Migration function for metadata to PostgreSQL
def migrate_metadata_to_postgres(sqlite_path, postgres_url):
    """
    Migrate Calibre metadata.db from SQLite to PostgreSQL
    """
    import sqlite3
    from sqlalchemy import create_engine, text
    
    log.info(f"Starting migration from {sqlite_path} to PostgreSQL")
    
    try:
        # Connect to SQLite database
        sqlite_conn = sqlite3.connect(sqlite_path)
        sqlite_conn.row_factory = sqlite3.Row
        sqlite_cur = sqlite_conn.cursor()
        
        # Connect to PostgreSQL
        postgres_engine = create_engine(postgres_url, pool_pre_ping=True)
        postgres_conn = postgres_engine.connect()
        
        # Begin transaction
        transaction = postgres_conn.begin()
        
        try:
            # Get all tables from SQLite
            sqlite_cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = [row[0] for row in sqlite_cur.fetchall()]
            
            log.info(f"Found tables to migrate: {tables}")
            
            for table in tables:
                log.info(f"Migrating table: {table}")
                
                # Get table schema from SQLite
                sqlite_cur.execute(f"PRAGMA table_info({table})")
                columns = sqlite_cur.fetchall()
                
                # Drop table if exists in PostgreSQL (be careful with this in production)
                postgres_conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
                
                # Create table in PostgreSQL
                column_defs = []
                for col in columns:
                    col_name = col[1]
                    col_type = col[2].upper()
                    col_notnull = col[3]
                    col_pk = col[5]
                    
                    # Map SQLite types to PostgreSQL types
                    if 'INT' in col_type:
                        pg_type = 'INTEGER'
                    elif 'TEXT' in col_type or 'CHAR' in col_type or 'CLOB' in col_type:
                        pg_type = 'TEXT'
                    elif 'REAL' in col_type or 'FLOAT' in col_type or 'DOUBLE' in col_type:
                        pg_type = 'REAL'
                    elif 'BLOB' in col_type:
                        pg_type = 'BYTEA'
                    elif 'BOOL' in col_type or 'BOOLEAN' in col_type:
                        pg_type = 'BOOLEAN'
                    else:
                        pg_type = 'TEXT'
                    
                    # Add PRIMARY KEY constraint
                    if col_pk:
                        pg_type += ' PRIMARY KEY'
                    elif col_notnull:
                        pg_type += ' NOT NULL'
                    
                    column_defs.append(f'"{col_name}" {pg_type}')
                
                create_table_sql = f'CREATE TABLE "{table}" ({", ".join(column_defs)})'
                postgres_conn.execute(text(create_table_sql))
                
                # Copy data
                sqlite_cur.execute(f'SELECT * FROM "{table}"')
                rows = sqlite_cur.fetchall()
                
                if rows:
                    col_names = [f'"{col[1]}"' for col in columns]
                    placeholders = ', '.join(['%s'] * len(col_names))
                    insert_sql = f'INSERT INTO "{table}" ({", ".join(col_names)}) VALUES ({placeholders})'
                    
                    for row in rows:
                        values = []
                        for col in columns:
                            col_name = col[1]
                            value = row[col_name]
                            
                            # Handle None values and data type conversions
                            if value is None:
                                values.append(None)
                            elif isinstance(value, bytes):
                                # Convert BLOB to bytes for PostgreSQL BYTEA
                                values.append(value)
                            else:
                                values.append(value)
                        
                        postgres_conn.execute(text(insert_sql), values)
                
                log.info(f"Migrated {len(rows)} rows from {table}")
            
            # Commit transaction
            transaction.commit()
            log.info("Migration completed successfully!")
            
        except Exception as e:
            transaction.rollback()
            log.error(f"Migration failed during table processing: {e}")
            raise
            
    except Exception as e:
        log.error(f"Migration failed: {e}")
        raise
    finally:
        # Clean up connections
        if 'sqlite_conn' in locals():
            sqlite_conn.close()
        if 'postgres_conn' in locals():
            postgres_conn.close()

def _configuration_update_helper():
    reboot_required = False
    to_save = request.form.to_dict()
    try:
        reboot_required |= _config_int(to_save, "config_port")
        reboot_required |= _config_string(to_save, "config_trustedhosts")
        reboot_required |= _config_string(to_save, "config_keyfile")
        if config.config_keyfile and not os.path.isfile(config.config_keyfile):
            return _configuration_result(_('Keyfile Location is not Valid, Please Enter Correct Path'))

        reboot_required |= _config_string(to_save, "config_certfile")
        if config.config_certfile and not os.path.isfile(config.config_certfile):
            return _configuration_result(_('Certfile Location is not Valid, Please Enter Correct Path'))

        _config_checkbox_int(to_save, "config_uploading")
        _config_checkbox_int(to_save, "config_unicode_filename")
        _config_checkbox_int(to_save, "config_embed_metadata")
        # Reboot on config_anonbrowse with enabled ldap, as decoraters are changed in this case
        reboot_required |= (_config_checkbox_int(to_save, "config_anonbrowse")
                            and config.config_login_type == constants.LOGIN_LDAP)
        _config_checkbox_int(to_save, "config_public_reg")
        _config_checkbox_int(to_save, "config_register_email")
        reboot_required |= _config_checkbox_int(to_save, "config_kobo_sync")
        _config_int(to_save, "config_external_port")
        _config_checkbox_int(to_save, "config_kobo_proxy")

        if "config_upload_formats" in to_save:
            to_save["config_upload_formats"] = ','.join(
                helper.uniq([x.lstrip().rstrip().lower() for x in to_save["config_upload_formats"].split(',')]))
            _config_string(to_save, "config_upload_formats")

        _config_string(to_save, "config_calibre")
        _config_string(to_save, "config_binariesdir")
        _config_string(to_save, "config_kepubifypath")
        if "config_binariesdir" in to_save:
            calibre_status = helper.check_calibre(config.config_binariesdir)
            if calibre_status:
                return _configuration_result(calibre_status)
            to_save["config_converterpath"] = get_calibre_binarypath("ebook-convert")
            _config_string(to_save, "config_converterpath")

        reboot_required |= _config_int(to_save, "config_login_type")

        # LDAP configurator
        if config.config_login_type == constants.LOGIN_LDAP:
            reboot, message = _configuration_ldap_helper(to_save)
            if message:
                return message
            reboot_required |= reboot

        # Remote login configuration
        _config_checkbox(to_save, "config_remote_login")
        if not config.config_remote_login:
            ub.session.query(ub.RemoteAuthToken).filter(ub.RemoteAuthToken.token_type == 0).delete()

        # Goodreads configuration
        _config_checkbox(to_save, "config_use_goodreads")
        _config_string(to_save, "config_goodreads_api_key")
        if services.goodreads_support:
            services.goodreads_support.connect(config.config_goodreads_api_key,
                                               config.config_use_goodreads)

        _config_int(to_save, "config_updatechannel")

        # Reverse proxy login configuration
        _config_checkbox(to_save, "config_allow_reverse_proxy_header_login")
        _config_string(to_save, "config_reverse_proxy_login_header_name")

        # OAuth configuration
        if config.config_login_type == constants.LOGIN_OAUTH:
            reboot_required |= _configuration_oauth_helper(to_save)

        # logfile configuration
        reboot, message = _configuration_logfile_helper(to_save)
        if message:
            return message
        reboot_required |= reboot

        # security configuration
        _config_checkbox(to_save, "config_check_extensions")
        _config_checkbox(to_save, "config_password_policy")
        _config_checkbox(to_save, "config_password_number")
        _config_checkbox(to_save, "config_password_lower")
        _config_checkbox(to_save, "config_password_upper")
        _config_checkbox(to_save, "config_password_character")
        _config_checkbox(to_save, "config_password_special")
        if 0 < int(to_save.get("config_password_min_length", "0")) < 41:
            _config_int(to_save, "config_password_min_length")
        else:
            return _configuration_result(_('Password length has to be between 1 and 40'))
        reboot_required |= _config_int(to_save, "config_session")
        reboot_required |= _config_checkbox(to_save, "config_ratelimiter")
        reboot_required |= _config_string(to_save, "config_limiter_uri")
        reboot_required |= _config_string(to_save, "config_limiter_options")

        # Rarfile Content configuration
        _config_string(to_save, "config_rarfile_location")
        if "config_rarfile_location" in to_save:
            unrar_status = helper.check_unrar(config.config_rarfile_location)
            if unrar_status:
                return _configuration_result(unrar_status)
    except (OperationalError, InvalidRequestError) as e:
        ub.session.rollback()
        log.error_or_exception("Settings Database error: {}".format(e))
        error_msg = str(e.orig) if hasattr(e, 'orig') else str(e)
        return _configuration_result(_("Oops! Database Error: %(error)s.", error=error_msg))

    config.save()
    # Explicitly reload config to ensure we have the latest data
    config.load()
    log.info("Configuration saved successfully")
    
    if reboot_required:
        web_server.stop(True)

    return _configuration_result(None, reboot_required)

def _configuration_result(error_flash=None, reboot=False):
    resp = {}
    if error_flash:
        log.error(error_flash)
        config.load()
        resp['result'] = [{'type': "danger", 'message': error_flash}]
    else:
        resp['result'] = [{'type': "success", 'message': _("Calibre-Web configuration updated")}]
    resp['reboot'] = reboot
    resp['config_upload'] = config.config_upload_formats
    return Response(json.dumps(resp), mimetype='application/json')

def _db_configuration_result(error_flash=None, gdrive_error=None):
    
    gdrive_authenticate = not is_gdrive_ready()
    gdrivefolders = []
    if not gdrive_error and config.config_use_google_drive:
        gdrive_error = gdriveutils.get_error_text()
    if gdrive_error and gdrive_support:
        log.error(gdrive_error)
        gdrive_error = _(gdrive_error)
        flash(gdrive_error, category="error")
    else:
        if not gdrive_authenticate and gdrive_support:
            gdrivefolders = gdriveutils.listRootFolders()

    if error_flash:
        log.error(error_flash)
        config.load()
        flash(error_flash, category="error")
    elif request.method == "POST" and not gdrive_error:
        flash(_("Database Settings updated"), category="success")
    
    # Log PostgreSQL configuration status
    _log_postgresql_config_status()
    
    log.info(f"Database configuration - config: {config}, show_authenticate_google_drive: {gdrive_authenticate}, gdriveError: {gdrive_error}, feature_support: {feature_support}")
    
    return render_title_template("config_db.html",
                                 config=config,
                                 show_authenticate_google_drive=gdrive_authenticate,
                                 gdriveError=gdrive_error,
                                 gdrivefolders=gdrivefolders,
                                 feature_support=feature_support,
                                 title=_("Database Configuration"), page="dbconfig")

def _log_postgresql_config_status():
    """Log PostgreSQL configuration status for admin debugging"""
    from dotenv import load_dotenv
    load_dotenv(get_env_path())

    db_user = os.getenv("DB_USERNAME")
    db_host = os.getenv("DB_HOST")
    db_port = os.getenv("DB_PORT")
    db_name_app = os.getenv("DATABASENAME_APP")
    
    if all([db_user, db_host, db_port, db_name_app]):
        log.info("PostgreSQL configuration detected via environment variables")
        log.info(f"Database Host: {db_host}:{db_port}")
        log.info(f"App Database: {db_name_app}")
        log.info(f"Database configured: {config.db_configured}")
    else:
        log.warning("Incomplete PostgreSQL environment variables detected")
        missing_vars = []
        if not db_user: missing_vars.append("DB_USERNAME")
        if not db_host: missing_vars.append("DB_HOST")
        if not db_port: missing_vars.append("DB_PORT")
        if not db_name_app: missing_vars.append("DATABASENAME_APP")
        log.warning(f"Missing environment variables: {', '.join(missing_vars)}")

def _handle_new_user(to_save, content, languages, translations, kobo_support):
    content.default_language = to_save["default_language"]
    content.locale = to_save.get("locale", content.locale)

    content.sidebar_view = sum(int(key[5:]) for key in to_save if key.startswith('show_'))
    if "show_detail_random" in to_save:
        content.sidebar_view |= constants.DETAIL_RANDOM

    content.role = constants.selected_roles(to_save)
    try:
        if not to_save["name"] or not to_save["email"] or not to_save["password"]:
            log.info("Missing entries on new user")
            raise Exception(_("Oops! Please complete all fields."))
        content.password = generate_password_hash(helper.valid_password(to_save.get("password", "")))
        content.email = check_email(to_save["email"])
        # Query username, if not existing, change
        content.name = check_username(to_save["name"])
        if to_save.get("kindle_mail"):
            content.kindle_mail = valid_email(to_save["kindle_mail"])
        if config.config_public_reg and not check_valid_domain(content.email):
            log.info("E-mail: {} for new user is not from valid domain".format(content.email))
            raise Exception(_("E-mail is not from valid domain"))
    except Exception as ex:
        flash(str(ex), category="error")
        return render_title_template("user_edit.html", new_user=1, content=content,
                                     config=config,
                                     translations=translations,
                                     languages=languages, title=_("Add new user"), page="newuser",
                                     kobo_support=kobo_support, registered_oauth=oauth_check)
    try:
        content.allowed_tags = config.config_allowed_tags
        content.denied_tags = config.config_denied_tags
        content.allowed_column_value = config.config_allowed_column_value
        content.denied_column_value = config.config_denied_column_value
        # No default value for kobo sync shelf setting
        content.kobo_only_shelves_sync = int(to_save.get("kobo_only_shelves_sync", 0) == "on")
        ub.session.add(content)
        ub.session.commit()
        flash(_("User '%(user)s' created", user=content.name), category="success")
        log.debug("User {} created".format(content.name))
        return redirect(url_for('admin.admin'))
    except IntegrityError:
        ub.session.rollback()
        log.error("Found an existing account for {} or {}".format(content.name, content.email))
        flash(_("Oops! An account already exists for this Email. or name."), category="error")
    except OperationalError as e:
        ub.session.rollback()
        log.error_or_exception("Settings Database error: {}".format(e))
        flash(_("Oops! Database Error: %(error)s.", error=e.orig), category="error")

def _delete_user(content):
    if ub.session.query(ub.User).filter(
        ub.User.role.op('&')(constants.ROLE_ADMIN) == constants.ROLE_ADMIN,
        ub.User.id != content.id
    ).count():
        if content.name != "Guest":
            # 🧹 Delete all related data for this user
            ub.session.query(ub.ReadBook).filter_by(user_id=content.id).delete()
            ub.session.query(ub.Downloads).filter_by(user_id=content.id).delete()
            for us in ub.session.query(ub.Shelf).filter_by(user_id=content.id):
                ub.session.query(ub.BookShelf).filter_by(shelf=us.id).delete()
            ub.session.query(ub.Shelf).filter_by(user_id=content.id).delete()
            ub.session.query(ub.Bookmark).filter_by(user_id=content.id).delete()

            # 🧩 Add this line to delete OAuth entries too
            ub.session.query(ub.OAuth).filter_by(user_id=content.id).delete()

            ub.session.query(ub.ArchivedBook).filter_by(user_id=content.id).delete()
            ub.session.query(ub.RemoteAuthToken).filter_by(user_id=content.id).delete()
            ub.session.query(ub.User_Sessions).filter_by(user_id=content.id).delete()
            ub.session.query(ub.KoboSyncedBooks).filter_by(user_id=content.id).delete()

            # Delete KoboReadingState and children
            kobo_entries = ub.session.query(ub.KoboReadingState).filter_by(user_id=content.id).all()
            for kobo_entry in kobo_entries:
                ub.session.delete(kobo_entry)

            # Finally delete the user itself
            ub.session.query(ub.User).filter_by(id=content.id).delete()

            ub.session_commit()
            log.info(f"User {content.name} deleted including OAuth links")
            return _("User '%(nick)s' deleted", nick=content.name)
        else:
            raise Exception(_("Can't delete Guest User"))
    else:
        raise Exception(_("No admin user remaining, can't delete user"))

def _handle_edit_user(to_save, content, languages, translations, kobo_support):
    if to_save.get("delete"):
        try:
            flash(_delete_user(content), category="success")
        except Exception as ex:
            log.error(ex)
            flash(str(ex), category="error")
        return redirect(url_for('admin.admin'))
    else:
        if not ub.session.query(ub.User).filter(ub.User.role.op('&')(constants.ROLE_ADMIN) == constants.ROLE_ADMIN,
                                                ub.User.id != content.id).count() and 'admin_role' not in to_save:
            log.warning("No admin user remaining, can't remove admin role from {}".format(content.name))
            flash(_("No admin user remaining, can't remove admin role"), category="error")
            return redirect(url_for('admin.admin'))

        val = [int(k[5:]) for k in to_save if k.startswith('show_')]
        sidebar, __ = get_sidebar_config()
        for element in sidebar:
            value = element['visibility']
            if value in val and not content.check_visibility(value):
                content.sidebar_view |= value
            elif value not in val and content.check_visibility(value):
                content.sidebar_view &= ~value

        if to_save.get("Show_detail_random"):
            content.sidebar_view |= constants.DETAIL_RANDOM
        else:
            content.sidebar_view &= ~constants.DETAIL_RANDOM

        old_state = content.kobo_only_shelves_sync
        content.kobo_only_shelves_sync = int(to_save.get("kobo_only_shelves_sync") == "on") or 0
        # 1 -> 0: nothing has to be done
        # 0 -> 1: all synced books have to be added to archived books, + currently synced shelfs
        # which don't have to be synced have to be removed (added to Shelf archive)
        if old_state == 0 and content.kobo_only_shelves_sync == 1:
            kobo_sync_status.update_on_sync_shelfs(content.id)
        if to_save.get("default_language"):
            content.default_language = to_save["default_language"]
        if to_save.get("locale"):
            content.locale = to_save["locale"]
        try:
            anonymous = content.is_anonymous
            content.role = constants.selected_roles(to_save)
            if anonymous:
                content.role |= constants.ROLE_ANONYMOUS
            else:
                content.role &= ~constants.ROLE_ANONYMOUS
                if to_save.get("password", ""):
                    content.password = generate_password_hash(helper.valid_password(to_save.get("password", "")))

            new_email = valid_email(to_save.get("email", content.email))
            if not new_email:
                raise Exception(_("Email can't be empty and has to be a valid Email"))
            if new_email != content.email:
                content.email = check_email(new_email)
            # Query username, if not existing, change
            if to_save.get("name", content.name) != content.name:
                if to_save.get("name") == "Guest":
                    raise Exception(_("Guest Name can't be changed"))
                content.name = check_username(to_save["name"])
            if to_save.get("kindle_mail") != content.kindle_mail:
                content.kindle_mail = valid_email(to_save["kindle_mail"]) if to_save["kindle_mail"] else ""
        except Exception as ex:
            log.error(ex)
            flash(str(ex), category="error")
            return render_title_template("user_edit.html",
                                         translations=translations,
                                         languages=languages,
                                         mail_configured=config.get_mail_server_configured(),
                                         kobo_support=kobo_support,
                                         new_user=0,
                                         content=content,
                                         config=config,
                                         registered_oauth=oauth_check,
                                         title=_("Edit User %(nick)s", nick=content.name),
                                         page="edituser")
    try:
        ub.session_commit()
        flash(_("User '%(nick)s' updated", nick=content.name), category="success")
    except IntegrityError as ex:
        ub.session.rollback()
        log.error("An unknown error occurred while changing user: {}".format(str(ex)))
        flash(_("Oops! An unknown error occurred. Please try again later."), category="error")
    except OperationalError as e:
        ub.session.rollback()
        log.error_or_exception("Settings Database error: {}".format(e))
        flash(_("Oops! Database Error: %(error)s.", error=e.orig), category="error")
    return ""

def extract_user_data_from_field(user, field):
    match = re.search(field + r"=([@\.\d\s\w-]+)", user, re.IGNORECASE | re.UNICODE)
    if match:
        return match.group(1)
    else:
        raise Exception("Could Not Parse LDAP User: {}".format(user))

def extract_dynamic_field_from_filter(user, filtr):
    match = re.search("([a-zA-Z0-9-]+)=%s", filtr, re.IGNORECASE | re.UNICODE)
    if match:
        return match.group(1)
    else:
        raise Exception("Could Not Parse LDAP Userfield: {}", user)

def extract_user_identifier(user, filtr):
    dynamic_field = extract_dynamic_field_from_filter(user, filtr)
    return extract_user_data_from_field(user, dynamic_field)