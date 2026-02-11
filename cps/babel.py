from babel import negotiate_locale
from flask_babel import Babel, Locale
from babel.core import UnknownLocaleError
from flask import request
from .cw_login import current_user

from . import logger

log = logger.create()

babel = Babel()


def get_locale(locale=None):
    # Priority 1: Check if a specific locale is passed
    if locale:
        return locale
    
    # Priority 2: Check cookie (from language toggle switch) - works for all users
    request_locale = request.cookies.get("get_my_ebook_locale")
    if request_locale:
        return request_locale
    
    # Priority 3: If user is logged in (not Guest), use their saved locale preference
    if current_user is not None and hasattr(current_user, "locale"):
        if current_user.name != 'Guest' and current_user.locale:
            return current_user.locale
    
    # Priority 4: Fallback to browser language preferences
    preferred = list()
    if request.accept_languages:
        for x in request.accept_languages.values():
            try:
                preferred.append(str(Locale.parse(x.replace('-', '_'))))
            except (UnknownLocaleError, ValueError) as e:
                log.debug('Could not parse locale "%s": %s', x, e)
    
    locale_value = negotiate_locale(preferred or ['en'], get_available_translations())
    return locale_value


def get_user_locale_language(user_language):
    return Locale.parse(user_language).get_language_name(get_locale())


def get_available_locale():
    return [Locale('en')] + babel.list_translations()


def get_available_translations():
    return set(str(item) for item in get_available_locale())
