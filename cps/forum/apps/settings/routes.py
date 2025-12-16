import os
from flask import render_template, url_for, redirect, Blueprint, request, flash, redirect, jsonify
from flask_login import login_required, current_user
from .form import AccountForm, ChangePasswordForm
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from flask import current_app as app
from cps.forum.src.utilities.functions import generate_random_str
from cps.forum.src.decorators.email_verified import email_verified
from cps.forum.src.mails.registration_mail import send_validation_email
from cps import ub


settings_blueprint = Blueprint("settings", __name__, template_folder="templates")

@settings_blueprint.route("/", methods=["GET", "POST"])
@login_required
def index():
    account_form = AccountForm()
    

    if account_form.validate_on_submit():
        email_changed = account_form.email.data != current_user.email

        # Update user attributes directly
        current_user.name = account_form.name.data
        current_user.email = account_form.email.data
        
        if email_changed:
            current_user.forum_email_verified_at = None
            # Main User model doesn't have confirmation_token, skipping for now
            # current_user.confirmation_token = generate_random_str(40)
        
        try:
            ub.session.commit()
            flash("Your account has been updated successfully", "success")
            
            if email_changed:
                flash("Your email has been changed. Please note: verification email is not yet implemented for the unified user system.", "warning")
                # send_validation_email(current_user)
                
        except Exception as e:
            ub.session.rollback()
            flash(f"Error updating account: {e}", "error")

        return redirect(url_for("settings.index"))

    account_form.name.data = current_user.name
    account_form.email.data = current_user.email

    return render_template("settings/index.html", form=account_form)


@login_required
@settings_blueprint.route('/password', methods=["GET", "POST"])
def password():

    password_form = ChangePasswordForm()

    if password_form.validate_on_submit():
        # Update password using werkzeug's generate_password_hash to match main app
        current_user.password = generate_password_hash(password_form.new_password.data)
        
        try:
            ub.session.commit()
            flash("Your password has been changed successfully", "success")
        except Exception as e:
            ub.session.rollback()
            flash(f"Error changing password: {e}", "error")

        return redirect(url_for("settings.password"))

    return render_template("settings/password.html", form=password_form)


def _error_response(message, status_code = 422):
    return jsonify({
        "errors": {
            "avatar": message
        }
    }), status_code

avatar_extensions = ("png", "jpeg", "jpg", "gif", "svg") 

@login_required
@settings_blueprint.route('avatar', methods=["POST"])
def avatar():

    avatar_file = request.files['avatar']

    if not avatar_file:
        flash("Please provide an image", category="error")
        return _error_response("Please provide an image")

    extension = avatar_file.filename.split(".")[-1].lower()

    if not extension or not extension in avatar_extensions:
        flash("Please provide a valid image", category="error")
        return _error_response("Please provide a valid image")

    avatar_name = generate_random_str(20) + '.' + extension
    avatar_file.save(os.path.join(app.config['AVATAR_FOLDER'], avatar_name))

    # Update forum_avatar column
    current_user.forum_avatar = avatar_name
    
    try:
        ub.session.commit()
        
        return jsonify({
            "avatar":  current_user.profile_picture
        })
    except Exception as e:
        ub.session.rollback()
        flash(f"Database error: {e}", category="error")
        return _error_response(f"Database error: {e}", 500)

