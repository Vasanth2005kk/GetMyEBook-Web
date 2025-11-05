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
#  along with this program. If not, see <http://www.gnu.org/licenses/>

import json
import secrets
from functools import wraps
from urllib.parse import quote, unquote

from flask import session, request, make_response, abort
from flask import Blueprint, flash, redirect, url_for
from flask_babel import gettext as _
from authlib.integrations.flask_client import OAuth
from .cw_login import login_user, current_user
from sqlalchemy.orm.exc import NoResultFound
from .usermanagement import user_login_required
from werkzeug.security import generate_password_hash

from . import constants, logger, config, app, ub
from datetime import datetime

oauth_check = {}
oauthblueprints = []
oauth = Blueprint('oauth', __name__)
log = logger.create()

# Initialize Authlib OAuth
oauth_client = OAuth(app)

def oauth_required(f):
    @wraps(f)
    def inner(*args, **kwargs):
        if config.config_login_type == constants.LOGIN_OAUTH:
            return f(*args, **kwargs)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            data = {'status': 'error', 'message': 'Not Found'}
            response = make_response(json.dumps(data, ensure_ascii=False))
            response.headers["Content-Type"] = "application/json; charset=utf-8"
            return response, 404
        abort(404)

    return inner


def register_oauth_blueprint(cid, show_name):
    oauth_check[cid] = show_name


def register_user_with_oauth(user=None):
    all_oauth = {}
    for oauth_key in oauth_check.keys():
        if str(oauth_key) + '_oauth_user_id' in session and session[str(oauth_key) + '_oauth_user_id'] != '':
            all_oauth[oauth_key] = oauth_check[oauth_key]
    if len(all_oauth.keys()) == 0:
        return
    if user is None:
        flash(_("Register with %(provider)s", provider=", ".join(list(all_oauth.values()))), category="success")
    else:
        for oauth_key in all_oauth.keys():
            # Find this OAuth token in the database, or create it
            query = ub.session.query(ub.OAuth).filter_by(
                provider=oauth_key,
                provider_user_id=session[str(oauth_key) + "_oauth_user_id"],
            )
            try:
                oauth_entry = query.one()
                oauth_entry.user_id = user.id
            except NoResultFound:
                # no found, return error
                return
            ub.session_commit("User {} with OAuth for provider {} registered".format(user.name, oauth_key))


def logout_oauth_user():
    for oauth_key in oauth_check.keys():
        if str(oauth_key) + '_oauth_user_id' in session:
            session.pop(str(oauth_key) + '_oauth_user_id')


def oauth_update_token(provider_id, token, provider_user_id):
    session[provider_id + "_oauth_user_id"] = provider_user_id
    session[provider_id + "_oauth_token"] = json.dumps(token)

    # Find this OAuth token in the database, or create it
    query = ub.session.query(ub.OAuth).filter_by(
        provider=provider_id,
        provider_user_id=provider_user_id,
    )
    try:
        oauth_entry = query.one()
        # update token
        oauth_entry.token = json.dumps(token)
    except NoResultFound:
        oauth_entry = ub.OAuth(
            provider=provider_id,
            provider_user_id=provider_user_id,
            token=json.dumps(token),
        )
    ub.session.add(oauth_entry)
    ub.session_commit()

    return True


def generate_state():
    """Generate a secure state token for OAuth"""
    state = secrets.token_urlsafe(16)
    session['oauth_state'] = state
    # log.info(f"all sessions : {session}")
    return state


def validate_state(state):
    """Validate the state token from OAuth callback"""
    # log.info(f"1  session datas {session}")
    stored_state = session.pop('oauth_state', None)
    # log.info(f"2 validate state function resivers session {stored_state} and session datas {session}")
    if stored_state is None:
        log.warning("No stored state found in session")
        return False
    if stored_state != state:
        log.warning(f"State mismatch: stored={stored_state}, received={state}")
        return False
    return True


def handle_sso_login(provider_id, provider_user_id, token, user_info, provider_name):
    """
    Handle SSO login - either login existing user or create new one
    """
    try:
        log.debug(f"Starting SSO login for {provider_name} user: {provider_user_id}")

        # First, check if we have an OAuth entry for this provider user
        oauth_entry = ub.session.query(ub.OAuth).filter_by(
            provider=provider_id,
            provider_user_id=provider_user_id,
        ).first()

        # If OAuth entry exists and has a user, log them in
        if oauth_entry and oauth_entry.user:
            login_user(oauth_entry.user)
            log.debug("SSO Login successful for existing OAuth user: '%s'", oauth_entry.user.name)
            flash(_("Success! You are now logged in as: %(nickname)s", nickname=oauth_entry.user.name), category="success")
            return redirect(url_for('web.index'))

        # Check if user exists by email
        email = user_info.get('email')
        if email:
            existing_user = ub.session.query(ub.User).filter(ub.User.email == email).first()
            if existing_user:
                # Link this OAuth to existing user and login
                if not oauth_entry:
                    oauth_entry = ub.OAuth(
                        provider=provider_id,
                        provider_user_id=provider_user_id,
                        token=json.dumps(token),
                        user_id=existing_user.id
                    )
                else:
                    oauth_entry.user_id = existing_user.id
                
                ub.session.add(oauth_entry)
                ub.session.commit()
                
                login_user(existing_user)
                log.debug("SSO Login successful for existing email user: '%s'", existing_user.name)
                flash(_("Success! You are now logged in as: %(nickname)s", nickname=existing_user.name), category="success")
                return redirect(url_for('web.index'))

        # Create new user from SSO data
        return create_user_from_sso(provider_id, provider_user_id, token, user_info, provider_name)

    except Exception as e:
        log.error("Error in handle_sso_login: %s", e)
        flash(_("SSO login failed. Please try again."), category="error")
        return redirect(url_for('web.login'))


def create_user_from_sso(provider_id, provider_user_id, token, user_info, provider_name):
    """
    Create a new user from SSO data
    """
    try:
        email = user_info.get('email')
        name = user_info.get('name') or user_info.get('login') or f"{provider_name}_user_{provider_user_id}"
        
        if not email:
            flash(_("Email is required for SSO registration"), category="error")
            return redirect(url_for('web.login'))

        # Check if username already exists
        existing_username = ub.session.query(ub.User).filter(ub.User.name == name).first()
        if existing_username:
            # Append provider user ID to make username unique
            name = f"{name}_{provider_user_id}"[:64]

        # Generate a random password for SSO users
        random_password = secrets.token_urlsafe(16)

        # Create new user
        new_user = ub.User()
        new_user.name = name[:64]  # Truncate to max length
        new_user.email = email
        new_user.password = generate_password_hash(random_password)
        new_user.role = config.config_default_role
        new_user.locale = config.config_default_locale
        new_user.sidebar_view = config.config_default_show
        new_user.default_language = config.config_default_language

        ub.session.add(new_user)
        ub.session.flush()  # Get the new user ID

        # Create OAuth entry
        oauth_entry = ub.OAuth(
            provider=provider_id,
            provider_user_id=provider_user_id,
            token=json.dumps(token),
            user_id=new_user.id
        )
        ub.session.add(oauth_entry)
        ub.session.commit()

        # Login the new user
        login_user(new_user)
        log.debug("SSO Registration and login successful for new user: '%s'", new_user.name)
        flash(_("Success! Account created and you are now logged in as: %(nickname)s", nickname=new_user.name), category="success")
        return redirect(url_for('web.index'))

    except Exception as e:
        ub.session.rollback()
        log.error("Error creating user from SSO: %s", e)
        flash(_("Failed to create account. Please try again or contact administrator."), category="error")
        return redirect(url_for('web.login'))


def get_oauth_status():
    status = []
    query = ub.session.query(ub.OAuth).filter_by(
        user_id=current_user.id,
    )
    try:
        oauths = query.all()
        for oauth_entry in oauths:
            status.append(int(oauth_entry.provider))
        return status
    except NoResultFound:
        return None


def unlink_oauth(provider):
    if request.host_url + 'me' != request.referrer:
        pass
    query = ub.session.query(ub.OAuth).filter_by(
        provider=provider,
        user_id=current_user.id,
    )
    try:
        oauth_entry = query.one()
        if current_user and current_user.is_authenticated:
            try:
                ub.session.delete(oauth_entry)
                ub.session.commit()
                logout_oauth_user()
                flash(_("Unlink to %(oauth)s Succeeded", oauth=oauth_check[provider]), category="success")
                log.info("Unlink to {} Succeeded".format(oauth_check[provider]))
            except Exception as ex:
                log.error_or_exception(ex)
                ub.session.rollback()
                flash(_("Unlink to %(oauth)s Failed", oauth=oauth_check[provider]), category="error")
    except NoResultFound:
        log.warning("oauth %s for user %d not found", provider, current_user.id)
        flash(_("Not Linked to %(oauth)s", oauth=provider), category="error")
    return redirect(url_for('web.profile'))


def generate_oauth_blueprints():
    if not ub.session.query(ub.OAuthProvider).count():
        for provider in ("github", "google"):
            oauthProvider = ub.OAuthProvider()
            oauthProvider.provider_name = provider
            oauthProvider.active = False
            ub.session.add(oauthProvider)
            ub.session_commit("{} Blueprint Created".format(provider))

    oauth_ids = ub.session.query(ub.OAuthProvider).all()
    
    # GitHub OAuth configuration
    ele1 = dict(
        provider_name='github',
        id=oauth_ids[0].id,
        active=oauth_ids[0].active,
        oauth_client_id=oauth_ids[0].oauth_client_id,
        oauth_client_secret=oauth_ids[0].oauth_client_secret,
        obtain_link='https://github.com/settings/developers'
    )
    
    # Google OAuth configuration  
    ele2 = dict(
        provider_name='google',
        id=oauth_ids[1].id,
        active=oauth_ids[1].active,
        oauth_client_id=oauth_ids[1].oauth_client_id,
        oauth_client_secret=oauth_ids[1].oauth_client_secret,
        obtain_link='https://console.developers.google.com/apis/credentials'
    )
    
    oauthblueprints.append(ele1)
    oauthblueprints.append(ele2)

    # Register OAuth clients with Authlib
    for element in oauthblueprints:
        if element['active'] and element['oauth_client_id'] and element['oauth_client_secret']:
            if element['provider_name'] == 'github':
                oauth_client.register(
                    name='github',
                    client_id=element['oauth_client_id'],
                    client_secret=element['oauth_client_secret'],
                    access_token_url='https://github.com/login/oauth/access_token',
                    authorize_url='https://github.com/login/oauth/authorize',
                    api_base_url='https://api.github.com/',
                    client_kwargs={'scope': 'user:email'},
                )
                register_oauth_blueprint(element['id'], element['provider_name'])
                log.info(f"GitHub OAuth provider registered: {element['oauth_client_id'][:10]}...")
                
            elif element['provider_name'] == 'google':
                oauth_client.register(
                    name='google',
                    client_id=element['oauth_client_id'],
                    client_secret=element['oauth_client_secret'],
                    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
                    client_kwargs={
                        'scope': 'openid email profile',
                        'prompt': 'select_account'
                    }
                )
                register_oauth_blueprint(element['id'], element['provider_name'])
                log.info(f"Google OAuth provider registered: {element['oauth_client_id'][:10]}...")
    
    return oauthblueprints


# Initialize OAuth blueprints if support is enabled
if ub.oauth_support:
    oauthblueprints = generate_oauth_blueprints()
    log.info("OAuth blueprints initialized with %d providers", len(oauthblueprints))


# GitHub OAuth Routes
@oauth.route('/link/github')
@oauth_required
def github_login():
    try:
        redirect_uri = url_for('oauth.github_callback', _external=True)
        log.info(f"GitHub OAuth redirect_uri: {redirect_uri}")
        
        # Generate state and pass it to authorize_redirect
        state = generate_state()
        log.debug(f"Generated GitHub state: {state}")
        return oauth_client.github.authorize_redirect(redirect_uri, state=state)
    except Exception as e:
        log.error(f"Error in GitHub login: {e}")
        flash(_('Failed to start GitHub authentication'), 'error')
        return redirect(url_for('web.login'))


@oauth.route('/auth/github/callback')
def github_callback():
    try:
        log.debug("GitHub callback received")
        
        # Get state from request args and validate it
        state = request.args.get('state')
        log.debug(f"Received GitHub state: {state}")
        
        if not validate_state(state):
            log.error("CSRF state validation failed for GitHub")
            flash(_('Security validation failed. Please try again.'), 'error')
            return redirect(url_for('web.login'))
        
        token = oauth_client.github.authorize_access_token()
        if not token:
            flash(_('Failed to get authorization token from GitHub'), 'error')
            return redirect(url_for('web.login'))
        
        log.debug("Successfully obtained GitHub access token")
        
        # Get user info from GitHub
        resp = oauth_client.github.get('user', token=token)
        if resp.status_code != 200:
            log.error(f"GitHub API error: {resp.status_code} - {resp.text}")
            flash(_('Failed to fetch user info from GitHub'), 'error')
            return redirect(url_for('web.login'))
            
        user_info = resp.json()
        log.debug(f"GitHub user info: {user_info}")
        
        # Get email if not provided in user info
        if not user_info.get('email'):
            log.debug("Fetching GitHub user emails")
            resp_email = oauth_client.github.get('user/emails', token=token)
            if resp_email.status_code == 200:
                emails = resp_email.json()
                primary_email = next((email for email in emails if email.get('primary')), None)
                if primary_email:
                    user_info['email'] = primary_email.get('email')
                    log.debug(f"Found primary email: {user_info['email']}")
        
        github_id = str(user_info['id'])
        email = user_info.get('email')
        name = user_info.get('name') or user_info.get('login')
        
        if not github_id:
            flash(_('Invalid user information received from GitHub'), 'error')
            return redirect(url_for('web.login'))

        log.debug(f"GitHub user - ID: {github_id}, Email: {email}, Name: {name}")

        # Update token and handle SSO login
        oauth_update_token(str(oauthblueprints[0]['id']), token, github_id)
        return handle_sso_login(str(oauthblueprints[0]['id']), github_id, token, user_info, 'GitHub')
        
    except Exception as e:
        log.error_or_exception(f"Error during GitHub OAuth callback: {e}")
        flash(_('Authentication failed: %(error)s', error=str(e)), 'error')
        return redirect(url_for('web.login'))


@oauth.route('/unlink/github', methods=["GET"])
@user_login_required
def github_login_unlink():
    return unlink_oauth(oauthblueprints[0]['id'])


# Google OAuth Routes
@oauth.route('/link/google')
@oauth_required
def google_login():
    try:
        redirect_uri = url_for('oauth.google_callback', _external=True)
        log.info(f"Google OAuth redirect_uri: {redirect_uri}")
        
        # Generate state and pass it to authorize_redirect
        state = generate_state()
        log.info(f"Generated Google state: {state}")
        return oauth_client.google.authorize_redirect(redirect_uri, state=state)
    except Exception as e:
        log.error(f"Error in Google login: {e}")
        flash(_('Failed to start Google authentication'), 'error')
        return redirect(url_for('web.login'))


@oauth.route('/auth/google/callback')
def google_callback():
    try:
        log.info("Google callback received")    
        log.info(f"get all session datas {session}")
        
        # Get state from request args and validate it
        state = request.args.get('state')
        log.info(f"Received Google state: {state}")
        
        if not validate_state(state):
            log.error("CSRF state validation failed for Google")
            flash(_('Security validation failed. Please try again.'), 'error')
            return redirect(url_for('web.login'))
        
        token = oauth_client.google.authorize_access_token()
        if not token:
            flash(_('Failed to get authorization token from Google'), 'error')
            return redirect(url_for('web.login'))
        
        log.info("Successfully obtained Google access token")
        
        # Get user info from the token
        user_info = token.get('userinfo')
        log.info(f"sso user info : {user_info}")
        if not user_info:
            # Fallback: fetch user info from Google API
            log.debug("Fetching user info from Google API")
            resp = oauth_client.google.get('userinfo', token=token)
            if resp.status_code != 200:
                log.error(f"Google API error: {resp.status_code} - {resp.text}")
                flash(_('Failed to fetch user info from Google'), 'error')
                return redirect(url_for('web.login'))
            user_info = resp.json()
       
        google_id = user_info.get('sub')
        email = user_info.get('email')
        name = user_info.get('name')

        if not google_id or not email:
            flash(_('Invalid user information received from Google'), 'error')
            return redirect(url_for('web.login'))

        log.debug(f"Google user - ID: {google_id}, Email: {email}, Name: {name}")

        # Update token and handle SSO login
        oauth_update_token(str(oauthblueprints[1]['id']), token, google_id)
        return handle_sso_login(str(oauthblueprints[1]['id']), google_id, token, user_info, 'Google')
        
    except Exception as e:
        log.error_or_exception(f"Error during Google OAuth callback: {e}")
        flash(_('Authentication failed: %(error)s', error=str(e)), 'error')
        return redirect(url_for('web.login'))


@oauth.route('/unlink/google', methods=["GET"])
@user_login_required
def google_login_unlink():
    return unlink_oauth(oauthblueprints[1]['id'])