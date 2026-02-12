"""
eGSIM Django settings file for development (local testing in the web browser)
"""
from egsim.settings.base import *

DEBUG = True

for template in TEMPLATES:
    template['OPTIONS']['debug'] = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = ')d#k&x(n_t_*3sgpe^e%ftw%2+xb8l3f%i^j77=ga-!9f)n$5m'

MEDIA_ROOT = Path(__file__).resolve().parent.parent.parent / 'media'

# path to the database file:
DATABASES['default']['NAME'] = MEDIA_ROOT / 'db.sqlite3'

