"""
eGSIM Django settings file for development (local testing in the web browser)
"""
from egsim.settings.base import *

DEBUG = True

for template in TEMPLATES:
    template['OPTIONS']['debug'] = True

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = ')d#k&x(n_t_*3sgpe^e%ftw%2+xb8l3f%i^j77=ga-!9f)n$5m'

# media root (only declared for clarity, to be implemented in sub-settings files):
MEDIA_ROOT = Path('~/Nextcloud/egsim-data').expanduser()

# Override Db path to be in media root (as long as the latter is not public):
DATABASES['default']['NAME'] = MEDIA_ROOT / "db.sqlite3"  # noqa