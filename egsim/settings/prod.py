"""
Django settings for production.

Configure required environment variables in your deployment environment (e.g. service
file)
"""

from egsim.settings.base import *  # Note: you also import pathlib.Path automatically
import os

DEBUG = False  # DO NOT CHANGE THIS IN PRODUCTION!

ALLOWED_HOSTS = ['egsim.gfz.de', 'egsim.gfz-potsdam.de']

CSRF_TRUSTED_ORIGINS = ["https://egsim.gfz.de", "https://egsim.gfz-potsdam.de"]

# trust a specific header (usually X-Forwarded-Proto) from your proxy (Nginx)
# to determine if the original request was HTTPS.
# Apparently, with this 'request.scheme' correctly displays 'https' in production
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# SECRET_KEY SHOULD BE UNIQUE FOR EACH SETTINGS FILE AND CAN BE GENERATED ON THE
# TERMINAL (WITHIN THE DJANGO VIRTUAL ENV)  WITH THE COMMAND:
# python -c "from django.core.management.utils import get_random_secret_key;print(get_random_secret_key())"  # noqa
SECRET_KEY = os.environ["EGSIM_SECRET_KEY"]

__DATA_ROOT__ = Path(os.environ['EGSIM_DATA_ROOT'])

# path to the sqlite database (you may place it next to MEDIA_ROOT)
DATABASES['default']['NAME'] = os.environ['EGSIM_DB_DEFAULT_NAME']

# media root (path on the server):
MEDIA_ROOT = os.environ['EGSIM_MEDIA_ROOT']

# static files root (path on the server)
STATIC_ROOT = os.environ['EGSIM_STATIC_ROOT']



