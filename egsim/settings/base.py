"""
eGSIM base Django settings file

This module defines the default configuration shared by all environments.
Other settings modules import from here:

from egsim.settings.base import *

And override only what differs. Django settings doc here:
https://docs.djangoproject.com/en/stable/ref/settings
"""
from pathlib import Path

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY: str

ALLOWED_HOSTS: list[str]

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG: bool  # default to False if not given

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # https://docs.djangoproject.com/en/stable/topics/db/models/#using-models
    'egsim.api',
    'egsim.app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware'
]

ROOT_URLCONF = 'egsim.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [Path(__file__).resolve().parent.parent / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'debug': False,
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
            'string_if_invalid': '"%s" NOT FOUND',
            # https://stackoverflow.com/a/35837135:
            'builtins': [
                'django.templatetags.static',
            ],
        },
    },
]

WSGI_APPLICATION = 'egsim.wsgi.application'

# Database
# https://docs.djangoproject.com/en/stable/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ''  # you will need to populate this in subclassed settings
    }
}

# Password validation, not used keep defaults here (see settings link above for help):

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',  # noqa
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization (not used keep defaults here, see settings link above for help)

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = False

# static files url:
STATIC_URL = '/static/'

# static root (only declared for clarity, to be implemented in sub-settings files).
# Note: While in development (DEBUG=True), STATIC_ROOT does nothing. You even don't
# need to set it. Django looks for static files inside each app's directory
# (djangoproject/appname/static) and then in STATICFILES_DIRS (if implemented) and
# serves them automatically (this is the magic done by manage.py runserver
# when DEBUG=True).
# When your project goes live (production), most likely you will serve
# dynamic content using Django and static files by Nginx / Apache, because the latter
# are incredibly efficient and will reduce the workload off Django.
# To do so, you
# 1) set STATIC_ROOT here so that when you run `manage.py collectstatic`
#    Django will copy static files from all the apps you have to STATIC_ROOT
# 2) you configure Nginx/Apache to look for static files in STATIC_ROOT
STATIC_ROOT: str

# media files url:
MEDIA_URL = '/media/'

# media root (only declared for clarity, to be implemented in sub-settings files):
MEDIA_ROOT: str

# If we have logins better to set this to True (in the meantime, set to False):
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

CSRF_USE_SESSIONS = True
CSRF_COOKIE_HTTPONLY = True
# CSRF_COOKIE_NAME = "csrftoken"
# CSRF_HEADER_NAME = "HTTP_X_CSRFTOKEN"  # "X-CSRFToken"

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Use a singleton, custom no-op renderer to speed up Forms and Errors initialization
FORM_RENDERER = 'egsim.api.forms.get_base_singleton_renderer'

# # Since Django 3.0. The default value of the X_FRAME_OPTIONS setting was changed
# # from SAMEORIGIN to DENY. If you want to restore it back uncomment:
# X_FRAME_OPTIONS = 'SAMEORIGIN'

# ==============================================================================
# NOTE: THE MAX FILE UPLOAD SIZE AND THE MAX TIMEOUT ARE HANDLED IN NGINX CONF!
# THE SETTINGS BELOW DO NOT HANDLE THESE ISSUES, READ THEIR DOCSTRING CAREFULLY!
# ==============================================================================

# The maximum size (in bytes) that an upload will be before it gets streamed to the
# file system. Set to 0 to force all uploaded files on disk because as of pandas 2.2.2
# HDF does not support reading from stream or buffer
FILE_UPLOAD_MAX_MEMORY_SIZE = 0  # for ref, 2621440 (2Mb) is the default in Django 5.1

# The maximum size in bytes (EXCLUDING THE FILE UPLOAD SIZE) that a request body may be
# before a SuspiciousOperation (RequestDataTooBig) is raised:
DATA_UPLOAD_MAX_MEMORY_SIZE: 5242880  # 5Mb (2621440 = 2Mb is the default in Django 5.1)
