"""
Django settings for eGSIM project.

Copied from https://djangodeployment.com/wp-content/uploads/2017/03/Django-deployment-cheatsheet.pdf

Copy this file in a specified folder of the server and replace all
variables ("$*") with the corresponding value
"""

from $DJANGO_PROJECT.settings_debug import *

DEBUG = False  # DO NOT CHANGE THIS!
ALLOWED_HOSTS = ['$DOMAIN', 'www.$DOMAIN']
# $SECRET_KEY CAN BE GENERATED ON THE TERMINAL (WITHIN THE DJANGO VIRUAL ENV)  WITH THE COMMAND:
# python -c "from django.core.management.utils import get_random_secret_key;print(get_random_secret_key())"
# COPY THE OTUPUT STRING HERE BELOW
SECRET_KEY = ''
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': '/var/opt/$DJANGO_PROJECT/$DJANGO_PROJECT.db',
    }
}
# static files root (path on the server)
STATIC_ROOT = '/var/cache/$DJANGO_PROJECT/static/'
# static files url:
# STATIC_URL = '/static/'

# media root (path on the server):
MEDIA_ROOT = '/var/opt/$DJANGO_PROJECT/media/'
# static files url:
# MEDIA_URL = '/media/'

# EMAIL configuration (disabled by default, uncomment if needed):
# SERVER_EMAIL = 'noreply@$DOMAIN'
# DEFAULT_FROM_EMAIL = 'noreply@$DOMAIN'
# ADMINS = [
#     ('$ADMIN_NAME', '$ADMIN_EMAIL_ADDRESS'),
# ]
# EMAIL_HOST = '$EMAIL_HOST'
# EMAIL_HOST_USER = '$EMAIL_USER'
# EMAIL_HOST_PASSWORD = '$EMAIL_PASSWORD'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
