from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func

from app.extensions import bcrypt, db, limiter, oauth
from app.models import User

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.get("/")
def index():
    return render_template(
        "auth/index.html",
        google_enabled=bool(oauth.create_client("google")),
        apple_enabled=bool(oauth.create_client("apple")),
    )


@bp.route("/register", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        full_name = (request.form.get("full_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""

        errors = _validate_registration(full_name, email, password, confirm_password)
        if errors:
            for message in errors:
                flash(message, "error")
            return render_template(
                "auth/register.html",
                full_name=full_name,
                email=email,
                google_enabled=bool(oauth.create_client("google")),
                apple_enabled=bool(oauth.create_client("apple")),
            )

        if User.query.filter(func.lower(User.email) == email).first():
            flash("An account with that email already exists.", "error")
            return render_template(
                "auth/register.html",
                full_name=full_name,
                email=email,
                google_enabled=bool(oauth.create_client("google")),
                apple_enabled=bool(oauth.create_client("apple")),
            )

        user = User(
            username=_build_unique_username(full_name or email.split("@")[0]),
            email=email,
            display_name=full_name,
            is_verified=False,
        )
        user.set_password(password, bcrypt)

        db.session.add(user)
        db.session.commit()

        login_user(user, remember=True)
        flash("Your account has been created.", "success")
        return redirect(url_for("dashboard.index"))

    return render_template(
        "auth/register.html",
        google_enabled=bool(oauth.create_client("google")),
        apple_enabled=bool(oauth.create_client("apple")),
    )


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("15 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        remember_me = request.form.get("remember_me") == "on"

        user = User.query.filter(func.lower(User.email) == email).first()
        if not user or not user.check_password(password, bcrypt):
            flash("Invalid email or password.", "error")
            return render_template(
                "auth/login.html",
                email=email,
                google_enabled=bool(oauth.create_client("google")),
                apple_enabled=bool(oauth.create_client("apple")),
            )

        user.last_login = datetime.now(timezone.utc)
        db.session.commit()

        login_user(user, remember=remember_me)
        flash("Signed in successfully.", "success")

        next_url = request.args.get("next")
        if next_url and next_url.startswith("/"):
            return redirect(next_url)
        return redirect(url_for("dashboard.index"))

    return render_template(
        "auth/login.html",
        google_enabled=bool(oauth.create_client("google")),
        apple_enabled=bool(oauth.create_client("apple")),
    )


@bp.post("/logout")
@login_required
def logout():
    logout_user()
    flash("Signed out.", "info")
    return redirect(url_for("home"))


@bp.get("/google")
def google_start():
    client = oauth.create_client("google")
    if not client:
        flash("Google login is not configured yet.", "info")
        return redirect(url_for("auth.login"))

    redirect_uri = url_for("auth.google_callback", _external=True, _scheme=current_app.config["PREFERRED_URL_SCHEME"])
    return client.authorize_redirect(redirect_uri)


@bp.get("/google/callback")
def google_callback():
    client = oauth.create_client("google")
    if not client:
        flash("Google login is not configured yet.", "info")
        return redirect(url_for("auth.login"))

    token = client.authorize_access_token()
    userinfo = token.get("userinfo")
    if not userinfo:
        userinfo = client.userinfo(token=token)

    user = _create_or_update_oauth_user(
        provider="google",
        provider_sub=str(userinfo.get("sub") or ""),
        email=(userinfo.get("email") or "").lower(),
        display_name=userinfo.get("name") or userinfo.get("given_name") or "Google User",
        avatar_url=userinfo.get("picture"),
    )
    if not user:
        flash("Google login failed. Please try email login.", "error")
        return redirect(url_for("auth.login"))

    login_user(user, remember=True)
    flash("Signed in with Google.", "success")
    return redirect(url_for("dashboard.index"))


@bp.get("/apple")
def apple_start():
    client = oauth.create_client("apple")
    if not client:
        flash("Apple login is not configured yet.", "info")
        return redirect(url_for("auth.login"))

    redirect_uri = url_for("auth.apple_callback", _external=True, _scheme=current_app.config["PREFERRED_URL_SCHEME"])
    return client.authorize_redirect(redirect_uri)


@bp.route("/apple/callback", methods=["GET", "POST"])
def apple_callback():
    client = oauth.create_client("apple")
    if not client:
        flash("Apple login is not configured yet.", "info")
        return redirect(url_for("auth.login"))

    token = client.authorize_access_token()
    claims = client.parse_id_token(token)

    user = _create_or_update_oauth_user(
        provider="apple",
        provider_sub=str(claims.get("sub") or ""),
        email=(claims.get("email") or "").lower(),
        display_name=claims.get("name") or "Apple User",
    )
    if not user:
        flash("Apple login failed. Please try email login.", "error")
        return redirect(url_for("auth.login"))

    login_user(user, remember=True)
    flash("Signed in with Apple.", "success")
    return redirect(url_for("dashboard.index"))


def _validate_registration(full_name: str, email: str, password: str, confirm_password: str) -> list[str]:
    errors: list[str] = []

    if len(full_name) < 2:
        errors.append("Full name must be at least 2 characters.")

    if not email or "@" not in email or "." not in email.split("@")[-1]:
        errors.append("Enter a valid email address.")

    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")

    if not any(character.isdigit() for character in password):
        errors.append("Password must include at least one number.")

    if password != confirm_password:
        errors.append("Passwords do not match.")

    return errors


def _build_unique_username(seed: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", seed.lower()).strip("-")
    base = cleaned or "collector"
    candidate = base
    suffix = 1

    while User.query.filter_by(username=candidate).first():
        suffix += 1
        candidate = f"{base}-{suffix}"

    return candidate


def _create_or_update_oauth_user(
    provider: str,
    provider_sub: str,
    email: str,
    display_name: str,
    avatar_url: str | None = None,
) -> User | None:
    if not provider_sub or not email:
        return None

    user = User.query.filter_by(oauth_provider=provider, oauth_sub=provider_sub).first()
    if not user:
        user = User.query.filter(func.lower(User.email) == email).first()

    if not user:
        user = User(
            username=_build_unique_username(display_name or email.split("@")[0]),
            email=email,
            display_name=display_name,
            is_verified=True,
        )
        user.set_password(secrets.token_urlsafe(40), bcrypt)
        db.session.add(user)

    user.oauth_provider = provider
    user.oauth_sub = provider_sub
    user.display_name = display_name or user.display_name
    if avatar_url:
        user.avatar_url = avatar_url
    user.last_login = datetime.now(timezone.utc)

    db.session.commit()
    return user
