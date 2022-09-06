"""
Empty and (re)populate the database with all eGSIM required data.
This is also the RECOMMENDED command to be executed every time eGSIM
dependencies are upgraded, or new external source data is added.
See the README file in the "egsim/management/commands" directory for details

Usage:
```
export DJANGO_SETTINGS_MODULE="..."; python manage.py egsim_init
export DJANGO_SETTINGS_MODULE="..."; python manage.py egsim_init --dry-run
```

For further info see:
https://django.readthedocs.io/en/2.0.x/howto/custom-management-commands.html

Created on 6 Apr 2019

@author: rizac <at> gfz-potsdam.de
"""
from django.core.management import call_command, load_command_class, CommandError
from django.db import DatabaseError

from . import EgsimBaseCommand

# check JSON1 extension (it should be enabled in all newest OSs and Python versions):
from django.conf import settings


if any(_['ENGINE'] == 'django.db.backends.sqlite3' for _ in settings.DATABASES.values()):
    # sqlite is used, check JSON1 extension. Note that Django does also this
    # (JSONField) but for safety we perform the test again
    try:
        import sqlite3
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()
        cursor.execute('SELECT JSON(\'{"a": "b"}\')')
    except Exception:
        raise ValueError('JSON not supported in this SQLite version. To fix it, visit: '
                         'https://code.djangoproject.com/wiki/JSON1Extension')


# Define sub commands to be executed typing their module name:
APPNAME = 'egsim.api'
SUBCOMMANDS = [load_command_class(APPNAME, _) for _ in
               # ====================================================
               # IMPORTANT: TO AD NEW COMMANDS UPDATE THE LIST BELOW:
               # ====================================================
               ['_egsim_oq', '_egsim_reg', '_egsim_flatfiles']]


class Command(EgsimBaseCommand):
    """Class implementing the command functionality"""

    # As help, use the module docstring (until the first empty line),
    # then add the subcommands help:
    help = globals()['__doc__'].split("\n\n")[0]
    help += "\n".join([
        '\nThis command performs in series the following operations:',
        "\n\n".join(cmd.help for cmd in SUBCOMMANDS)
    ])

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
        parser.add_argument(
            '--dry-run', action='store_true', dest='dry-run',
            help=("Perform a rehearsal run and some checks with no "
                  "db modifications. Useful e.g. after an OpenQuake "
                  "upgrade")
        )

    def handle(self, *args, **options):
        """Execute the command"""

        if options.pop('dry-run', False):
            self.dry_run()
            return

        self.printinfo('')
        self.printinfo('Emptying and re-populating database tables')
        try:
            call_command('flush', *args, **options)
        except DatabaseError as db_err:
            # This might be due to the fact that the migration workflow has
            # not been performed. Append a hint to the error message:
            url = "https://docs.djangoproject.com/en/stable/topics/migrations/"
            raise CommandError('%s.\nDid you create the db first?\n(for '
                               'info see: %s)' % (str(db_err), url))

        options.pop('interactive', None)
        for cmd in SUBCOMMANDS:
            self.printinfo('')
            call_command(cmd, *args, **options)

    def dry_run(self):
        """Performs a dry run by just scanning the OpenQuake GSIMs, listing the
        Gground shaking models that have required parameter(s) not implemented
        in `gsim_params.yaml`, which makes the model(s) ignored in eGSIM.
        By implementing the parameters in the YAML file, you can decide whether
        to associate the parameter to a flatfile column and thus include the
        associated model(s) in eGSIM, or simply implement the parameter with no
        mapping, to deliberately ignore the associated model(s) and suppress
        the warning the next time this command is run
        """
        # put here all imports not needed by the module:
        from openquake.hazardlib.gsim import get_available_gsims
        import inspect
        import os

        cwd = os.getcwd()
        relpath = lambda path: f"'{os.path.relpath(path, cwd)}'"

        # checking flatfiles
        from ._egsim_flatfiles import SRC_DIR, DEST_DIR, Command as cmd
        parsers = cmd.PARSERS
        self.printinfo(f'')
        self.printinfo(f'[Flatfiles]')
        self.printinfo(f'Source dir (CSV files): {relpath(SRC_DIR)} but might be '
                       f'different for big flatfiles that cannot be committed')
        self.printinfo(f'Destination dir (HDF files): {relpath(DEST_DIR)}')
        self.printinfo(f'Found {len(parsers)} pre-defined flatfile(s) '
                       f'to be written as HDF:')
        for i, (fpath, parser) in enumerate(parsers.items(), 1):
            self.printinfo(f'{i:>3}) {relpath(fpath)}')
            self.printinfo(f'     Parser class: {parser.__module__}.{parser.__name__}')

        # checking regionalizations
        from ._egsim_reg import SRC_DIR, Command as cmd
        regs = list(cmd.get_data_files())
        self.printinfo(f'')
        self.printinfo(f'[Regionalizations]')
        self.printinfo(f'Source dir (JSON+geoJSON files): {relpath(SRC_DIR)}')
        self.printinfo(f'Destination DB: {settings.DATABASES["default"]["NAME"]}')
        self.printinfo(f'Found {len(regs)} regionalizations: '
                       f'{", ".join(_[0] for _ in regs)}')

        from ._egsim_oq import read_gsim_params, GSIM_PARAMS_YAML_PATH
        self.printinfo(f'')
        self.printinfo(f'[GSIM parameters]')
        self.printinfo('Scanning OpenQuake '
                       f'model parameters and parameters registered in '
                       f'{relpath(GSIM_PARAMS_YAML_PATH)}')
        registered_params = read_gsim_params()
        oq_atts = set(_.split('.', 1)[0] for _ in registered_params)
        already_done = set()
        ret = 0
        for gsim_name, gsim in get_available_gsims().items():
            if inspect.isabstract(gsim):
                continue
            for oq_att in oq_atts:
                for param in getattr(gsim, oq_att) or []:
                    key = "%s.%s" % (oq_att, param)
                    if key in already_done:
                        continue
                    already_done.add(key)
                    if key not in registered_params:
                        ret = 1
                        self.printwarn('Warning: %s not defined in YAML' % key)
                    else:
                        registered_params.pop(key)

        for key in registered_params:
            ret = 1
            self.printwarn('Warning: %s in YAML not defined as OpenQuake '
                           'attribute' % key)

        if ret == 0:
            self.printinfo('YAML file is ok')
        self.printinfo(f'')
        return ret


def read_gsim_params() -> dict[str, dict]:
    """Reads the content of `gsim_params.yaml` where all GSIM parameters
    have been registered
    """
    import os
    import yaml
    GSIM_PARAMS_YAML_PATH = \
        os.path.join(os.path.abspath(os.path.dirname(os.path.dirname(__file__))),
                     "gsim_params.yaml")
    model_params: dict[str, dict] = {}
    with open(GSIM_PARAMS_YAML_PATH) as fpt:
        root_dict = yaml.safe_load(fpt)
        for param_type, params in root_dict.items():
            for param_name, props in params.items():
                model_params[f'{param_type}.{param_name}'] = props
    return model_params