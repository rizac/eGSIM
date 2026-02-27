"""
Django settings TEMPLATE for production.
Copy / paste it in a secure server location
and edit missing data (see declared variables below)
As convention, you may rename the production file `settings.py`
"""

from egsim.settings.base import *

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
SECRET_KEY: str

# path to the sqlite database (can be placed next to MEDIA_ROOT, see below)
DATABASES['default']['NAME']: str

# media root (path on the server):
MEDIA_ROOT: str

# static files root (path on the server)
STATIC_ROOT: str



