"""
Base Django settings for testing the eGSIM project.
"""
from egsim.settings.base import *


SECRET_KEY = 'test_secret_key'

DEGUG = False

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

# Database
# https://docs.djangoproject.com/en/stable/ref/settings/#databases

DATABASES['default']['NAME'] = ':memory:'

# media dir:
MEDIA_ROOT = (
        Path(__file__).resolve().parent.parent.parent /
        'tests' / 'django' / 'data' / 'media_root'
)
