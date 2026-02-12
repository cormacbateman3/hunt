"""Centralized configuration classes."""

import os

from dotenv import load_dotenv


load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    SECURITY_FORCE_HTTPS = _env_bool("SECURITY_FORCE_HTTPS", True)
    PREFERRED_URL_SCHEME = "https" if SECURITY_FORCE_HTTPS else "http"

    # x-forwarded-* trust count. Keep at 0 for direct-to-instance; set to 1+ behind ALB/CloudFront.
    TRUSTED_PROXY_COUNT = _env_int("TRUSTED_PROXY_COUNT", 1)

    # Deployment profile is metadata used by ops/docs. It does not change behavior by itself.
    DEPLOYMENT_PROFILE = os.getenv("DEPLOYMENT_PROFILE", "dev")
    AWS_NETWORK_MODE = os.getenv("AWS_NETWORK_MODE", "single-instance-public")

    MAIL_SERVER = os.getenv("MAIL_SERVER", "localhost")
    MAIL_PORT = _env_int("MAIL_PORT", 1025)
    MAIL_USE_TLS = _env_bool("MAIL_USE_TLS", False)
    MAIL_USE_SSL = _env_bool("MAIL_USE_SSL", False)
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")

    RATELIMIT_DEFAULT = os.getenv("RATELIMIT_DEFAULT", "200 per day;50 per hour")
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = _env_bool("RATELIMIT_HEADERS_ENABLED", True)

    OAUTH_GOOGLE_CLIENT_ID = os.getenv("OAUTH_GOOGLE_CLIENT_ID")
    OAUTH_GOOGLE_CLIENT_SECRET = os.getenv("OAUTH_GOOGLE_CLIENT_SECRET")
    OAUTH_APPLE_CLIENT_ID = os.getenv("OAUTH_APPLE_CLIENT_ID")
    OAUTH_APPLE_CLIENT_SECRET = os.getenv("OAUTH_APPLE_CLIENT_SECRET")


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SECURITY_FORCE_HTTPS = _env_bool("SECURITY_FORCE_HTTPS", False)
    PREFERRED_URL_SCHEME = "https" if SECURITY_FORCE_HTTPS else "http"
    TRUSTED_PROXY_COUNT = _env_int("TRUSTED_PROXY_COUNT", 0)
    SQLALCHEMY_DATABASE_URI = os.getenv("DEV_DATABASE_URL", "sqlite:///keystonebid-dev.db")


class LaunchConfig(BaseConfig):
    """
    Lowest-cost launch profile.
    Designed for single EC2 or basic container host with no NAT/ALB requirement.
    """

    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SECURITY_FORCE_HTTPS = _env_bool("SECURITY_FORCE_HTTPS", False)
    PREFERRED_URL_SCHEME = "https" if SECURITY_FORCE_HTTPS else "http"
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", SECURITY_FORCE_HTTPS)
    REMEMBER_COOKIE_SECURE = _env_bool("REMEMBER_COOKIE_SECURE", SECURITY_FORCE_HTTPS)


class TestingConfig(BaseConfig):
    TESTING = True
    SECURITY_FORCE_HTTPS = False
    PREFERRED_URL_SCHEME = "http"
    TRUSTED_PROXY_COUNT = 0
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite:///keystonebid-test.db")
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    RATELIMIT_STORAGE_URI = "memory://"


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SECURITY_FORCE_HTTPS = _env_bool("SECURITY_FORCE_HTTPS", True)
    PREFERRED_URL_SCHEME = "https"
    SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", True)
    REMEMBER_COOKIE_SECURE = _env_bool("REMEMBER_COOKIE_SECURE", True)
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": _env_int("DB_POOL_RECYCLE_SECONDS", 1800),
        "pool_size": _env_int("DB_POOL_SIZE", 5),
        "max_overflow": _env_int("DB_MAX_OVERFLOW", 5),
    }


CONFIG_MAP = {
    "development": "config.DevelopmentConfig",
    "dev": "config.DevelopmentConfig",
    "testing": "config.TestingConfig",
    "test": "config.TestingConfig",
    "launch": "config.LaunchConfig",
    "lowcost": "config.LaunchConfig",
    "production": "config.ProductionConfig",
    "prod": "config.ProductionConfig",
    "scale": "config.ProductionConfig",
}


def resolve_config_path() -> str:
    explicit = os.getenv("APP_CONFIG")
    if explicit:
        return explicit
    profile = os.getenv("DEPLOYMENT_PROFILE", "development").strip().lower()
    return CONFIG_MAP.get(profile, "config.DevelopmentConfig")
