"""
Django settings for eGSIM project TEMPLATE for production.
On the production server, copy-paste the content of this file into
<eGSIM_REPO>/settings.py
and modify that file
(Note: for safety, settings.py is git-ignored)
"""

from egsim.settings.base import *

DEBUG = False  # For safety, reinforce debug False. DO NOT CHANGE THIS!

ALLOWED_HOSTS = ['egsim.gfz.de', 'egsim.gfz-potsdam.de']

CSRF_TRUSTED_ORIGINS = ["https://egsim.gfz.de", "https://egsim.gfz-potsdam.de"]

# trust a specific header (usually X-Forwarded-Proto) from your proxy (Nginx) to
# determine if the original request was HTTPS.
# Apparently, with this 'request.scheme' correctly displays 'https' in production
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')


############################################################
# SENSITIVE VARIABLES TO BE OVERWRITTEN ON HOSTING SERVER: #
############################################################

# SECRET_KEY can be generated with th command :
# python -c "from django.core.management.utils import get_random_secret_key;print(get_random_secret_key())"  # noqa
SECRET_KEY: str


# path to the database file:
DATABASES['default']['NAME'] = ''

# static files root (path on the server, staticfiles from this repo will be copied there
# in order to be served by Nginx / Apache, that must be configured)
STATIC_ROOT = ''

# media root (path on the server. In eGSIM, media root hilds flatfiles and
# regionalizations):
MEDIA_ROOT = ''

