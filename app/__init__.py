"""Flask application factory for KeystoneBid."""

from importlib import import_module

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app.extensions import bcrypt, db, limiter, login_manager, mail, migrate, oauth

BLUEPRINTS = [
    "auth",
    "listings",
    "bids",
    "search",
    "payments",
    "dashboard",
    "collector",
    "education",
    "stories",
    "admin",
    "api",
]


def create_app(config_object: str = "config.DevelopmentConfig") -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.wsgi_app = ProxyFix(  # type: ignore[assignment]
        app.wsgi_app,
        x_for=app.config.get("TRUSTED_PROXY_COUNT", 1),
        x_proto=app.config.get("TRUSTED_PROXY_COUNT", 1),
        x_host=app.config.get("TRUSTED_PROXY_COUNT", 1),
        x_port=app.config.get("TRUSTED_PROXY_COUNT", 1),
    )

    _register_extensions(app)
    _configure_oauth(app)
    _register_blueprints(app)

    @app.get("/")
    def home():
        from flask import render_template

        return render_template("home.html")

    return app


def _register_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    bcrypt.init_app(app)
    mail.init_app(app)
    limiter.init_app(app)
    oauth.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"


def _configure_oauth(app: Flask) -> None:
    google_client_id = app.config.get("OAUTH_GOOGLE_CLIENT_ID")
    google_client_secret = app.config.get("OAUTH_GOOGLE_CLIENT_SECRET")
    if google_client_id and google_client_secret:
        oauth.register(
            name="google",
            client_id=google_client_id,
            client_secret=google_client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )

    apple_client_id = app.config.get("OAUTH_APPLE_CLIENT_ID")
    apple_client_secret = app.config.get("OAUTH_APPLE_CLIENT_SECRET")
    if apple_client_id and apple_client_secret:
        oauth.register(
            name="apple",
            client_id=apple_client_id,
            client_secret=apple_client_secret,
            server_metadata_url="https://appleid.apple.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email name", "response_mode": "form_post"},
        )


def _register_blueprints(app: Flask) -> None:
    for blueprint_name in BLUEPRINTS:
        module = import_module(f"app.blueprints.{blueprint_name}.routes")
        app.register_blueprint(module.bp)


@login_manager.user_loader
def load_user(user_id: str):
    from app.models.user import User

    return User.query.get(int(user_id))
