"""
eGSIM management command. See `Command.help` for details
"""

from django.core.management import (call_command, load_command_class,
                                    BaseCommand)

# check JSON1 extension (it should be enabled in all newest OSs and Python versions):
from django.conf import settings


if any(_['ENGINE'] == 'django.db.backends.sqlite3'
       for _ in settings.DATABASES.values()):
    # sqlite is used, check JSON1 extension. Note that Django does also this
    # (JSONField) but for safety we perform the test again
    try:
        import sqlite3
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        cursor.execute('SELECT JSON(\'{"a": "b"}\')')
    except Exception:
        raise ValueError('JSON not supported in this SQLite version. To fix '
                         'it, visit: '
                         'https://code.djangoproject.com/wiki/JSON1Extension')


class Command(BaseCommand):

    help = """Empty and repopulates the eGSIM database"""

    def add_arguments(self, parser):
        """Implement here specific command options (this method is called
        automatically by the superclass)
        :param parser: :class:`argparse.ArgumentParser` instance
        """
        # For compatibility with the `flush` command (=empty db tables) which
        # is called first, add the flag(s) '--noinput' (or '--no-input'), and
        # store it in the variable `interactive`. This means that the flag
        # value will be accessible in `self.handle(... options)` via
        # `options["interactive"]`. `action='store_false'` means that the flag
        # value is False when *present*, and thus `options["interactive"]` is
        # True by default.
        parser.add_argument(
            '--noinput', '--no-input', action='store_false', dest='interactive',
            help='Do NOT prompt the user for input of any kind.',
        )

    def handle(self, *args, **options):
        """Execute the command"""

        self.stdout.write('')
        self.stdout.write('Empty and populating the eGSIM database')
        self.stdout.write('Remember that you can always inspect the database on '
                          'the browser via the Django admin panel (see README '
                          'file for info)')
        # remove interactive
        if options.pop('interactive', False) and \
                input('Do you want to continue (y/n)?') != 'y':
            return
        self.stdout.write('')

        # We cannot call `call_command` with the simple command name (str) because
        # they might be hidden (starting with underscore), we have to pass the command
        # class, which can be retrieved via `load_command_class`:
        app_name = 'egsim.api'
        call_command(load_command_class(app_name, '_egsim_openquake'),
                     *args, **options)
        self.stdout.write('')
        call_command(load_command_class(app_name, '_egsim_regionalizations'),
                     *args, **options)
        self.stdout.write('')
        call_command(load_command_class(app_name, '_egsim_flatfiles'),
                     *args, **options)
        self.stdout.write('')
