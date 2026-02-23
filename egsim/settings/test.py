"""
eGSIM Django settings file for testing (pytes-django)
"""
from egsim.settings.base import *


SECRET_KEY = 'test_secret_key'

DEBUG = False

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

DATABASES['default']['NAME'] = ':memory:'  # it's already :memory: but just for safety

# media dir:
MEDIA_ROOT = (
    Path(__file__).resolve().parent.parent.parent /
    'tests' / 'django' / 'data' / 'media_root'
)
