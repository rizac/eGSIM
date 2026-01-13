"""
Base Django settings for eGSIM project.

This file is supposed to be **overwritten** in dev / test / production, so take care to
overwrite relevant variable in the latter (replace SECRET_KEY, DEBUG=False and so on)

Info here:
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


# static files root (path on the server) I GUESS it is not used at all in development
# mode. In production, it is used as URL to retreive static files, if they
# are hosted on some machine (e.g. AWS), or by some server on the same
# machine (after configuring Nginx accordingly to serve static files at this url):
STATIC_URL = '/static/'

# While in development (debug=True), STATIC_ROOT does nothing. You even don't
# need to set it. Django looks for static files inside each app's directory
# (djangoproject/appname/static) and then in STATICFILES_DIRS (see below) and
# serves them automatically (this is the magic done by manage.py runserver
# when DEBUG=True). Note that in our case djangoproject = appname = egsim.
# When your project goes live, things differ. Most likely you will serve
# dynamic content using Django and static files will be served by Nginx. Why?
# Because Nginx is incredibly efficient and will reduce the workload off Django.
# This is where STATIC_ROOT becomes handy, as Nginx doesn't know anything about
# our django project and doesn't know where to find static files.
# So you set STATIC_ROOT = '/some/folder/' and tell Nginx to look for static
# files in /some/folder/. Then you run manage.py collectstatic and Django
# will copy static files from all the apps you have to /some/folder/.
# STATIC_ROOT = ''

# STATICFILES_DIRS is used to include additional directories for collectstatic
# to look for, and in development (debug=True) to search for static files
# in *addition* to the default djangoproject/appname/static.
# To keep things simple because we have just one django  project and one app
# (both named 'egsim') we do not want to tie any static file to a particular app,
# thus we adopt a very common approach: store static files under
# 'djangoproject/static' folder, which has the only drawback that we have to
# add the path to STATICFILES_DIRS
# STATICFILES_DIRS = (
#      os.path.join(BASE_DIR, 'static'),
# )

# static files url:
MEDIA_URL = '/media/'

# media dir:
# MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

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
