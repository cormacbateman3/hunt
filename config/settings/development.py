"""
Django development settings for Backtag project.
"""

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '.ngrok.io']


# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Email backend for development (console output)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


# Static files in development
#
# base.py configures WhiteNoise with a *manifest* storage, which is right for
# production and wrong here for two reasons:
#
#   1. WhiteNoise reads every static file into memory once, at process start.
#      Django re-reads templates on every request when DEBUG is on, so an
#      edited stylesheet would go on being served stale — new HTML, old CSS —
#      until the server was restarted. That is a genuinely confusing failure
#      because the page changes and the styling does not.
#   2. The manifest means `collectstatic` has to be re-run before an edited
#      file is visible at all.
#
# Autorefresh re-stats the file on each request, and the plain storage drops
# the manifest, so editing a stylesheet and reloading the page is enough.
WHITENOISE_AUTOREFRESH = True
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'

# Django Debug Toolbar (optional - uncomment if you want to use it)
# INSTALLED_APPS += ['debug_toolbar']
# MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] + MIDDLEWARE
# INTERNAL_IPS = ['127.0.0.1']
