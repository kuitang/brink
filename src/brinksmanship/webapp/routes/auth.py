"""Authentication routes."""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from ..extensions import db
from ..models.user import User

bp = Blueprint("auth", __name__, url_prefix="/auth")

MIN_PASSWORD_LENGTH = 8


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Handle user login."""
    if current_user.is_authenticated:
        return redirect(url_for("lobby.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        # Use same error message for invalid user vs invalid password
        if user is None or not user.check_password(password):
            flash("Invalid username or password.", "error")
            return render_template("pages/login.html")

        login_user(user)
        next_page = request.args.get("next")
        if next_page:
            return redirect(next_page)
        return redirect(url_for("lobby.index"))

    return render_template("pages/login.html")


@bp.route("/register", methods=["GET", "POST"])
def register():
    """Handle user registration."""
    if current_user.is_authenticated:
        return redirect(url_for("lobby.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        # Validation
        errors = []
        if not username:
            errors.append("Username is required.")
        elif len(username) < 3:
            errors.append("Username must be at least 3 characters.")
        elif len(username) > 64:
            errors.append("Username must be at most 64 characters.")

        if not password:
            errors.append("Password is required.")
        elif len(password) < MIN_PASSWORD_LENGTH:
            errors.append(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")

        if password != confirm:
            errors.append("Passwords do not match.")

        if User.query.filter_by(username=username).first():
            errors.append("Username already taken.")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("pages/register.html", username=username)

        # Create user
        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("pages/register.html")


@bp.route("/logout")
@login_required
def logout():
    """Handle user logout."""
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
