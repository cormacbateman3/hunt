"""Flask application factory for KeystoneBid."""

from importlib import import_module

from flask import Flask

from app.extensions import bcrypt, db, limiter, login_manager, mail, migrate

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

    _register_extensions(app)
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

    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"


def _register_blueprints(app: Flask) -> None:
    for blueprint_name in BLUEPRINTS:
        module = import_module(f"app.blueprints.{blueprint_name}.routes")
        app.register_blueprint(module.bp)


@login_manager.user_loader
def load_user(user_id: str):
    from app.models.user import User

    return User.query.get(int(user_id))
