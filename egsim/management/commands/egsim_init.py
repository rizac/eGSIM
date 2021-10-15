"""
Empty and (re)populate the database with all eGSIM required data.
This is also the RECOMMENDED command to be executed every time eGSIM
dependencies are upgraded, or new external source data is added.
See the README file in the "egsim/management/commands" directory for details

Usage:
```
export DJANGO_SETTINGS_MODULE="..."; python manage.py egsim_init
```

For further info see:
https://django.readthedocs.io/en/2.0.x/howto/custom-management-commands.html

Created on 6 Apr 2019

@author: rizac <at> gfz-potsdam.de
"""
from django.core.management import call_command, load_command_class, CommandError
from django.db import DatabaseError

from egsim.management.commands import EgsimBaseCommand

# check JSON1 extension (it should be enabled in all newest OSs and Python versions):
from django.conf import settings
if any(_['ENGINE'] == 'django.db.backends.sqlite3' for _ in settings.DATABASES.values()):
    # sqlite is used, check JSON1 extension:
    try:
        import sqlite3
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        cursor.execute('SELECT JSON(\'{"a": "b"}\')')
    except Exception:
        raise ValueError('JSON1 not supported in this SQLite version. To fix it, visit: '
                         'https://code.djangoproject.com/wiki/JSON1Extension')


# Define sub commands to be executed typing their module name:
APPNAME = 'egsim'
SUBCOMMANDS = [load_command_class(APPNAME, _) for _ in
               # ====================================================
               # IMPORTANT: TO AD NEW COMMANDS UPDATE THE LIST BELOW:
               # ====================================================
               ['_egsim_oq', 'egsim_reg']]


class Command(EgsimBaseCommand):
    """Class implementing the command functionality"""

    # As help, use the module docstring (until the first empty line),
    # then add the subcommands help:
    help = globals()['__doc__'].split("\n\n")[0]
    help += "\n".join([
        '\nThis command performs in series the following operations:',
        "\n\n".join(cmd.help for cmd in SUBCOMMANDS)
    ])

    def handle(self, *args, **options):
        """Execute the command"""

        try:
            call_command('flush', *args, **options)
        except DatabaseError as db_err:
            # This might be due to the fact that the migration workflow has
            # not been performed. Append a hint to the error message:
            url = "https://docs.djangoproject.com/en/stable/topics/migrations/"
            raise CommandError('%s.\nDid you create the db first?\n(for '
                               'info see: %s)' % (str(db_err), url))

        for cmd in SUBCOMMANDS:
            call_command(cmd, *args, **options)
