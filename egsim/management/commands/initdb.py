"""
Command to initialize and populate the database with all eGSIM required data.
This is also the RECOMMENDED command to be executed every time eGSIM
dependencies are upgraded, or new external source data is added.
See the README file in the "egsim/management/commands" directory for details

Usage:
```
export DJANGO_SETTINGS_MODULE="..."; python manage.py initdb
```

For further info see:
https://django.readthedocs.io/en/2.0.x/howto/custom-management-commands.html

Created on 6 Apr 2019

@author: riccardo
"""

from django.db.utils import OperationalError
from django.core.management.base import BaseCommand, CommandError

from egsim.models import empty_all
from ._utils import EgsimBaseCommand
from ...core.utils import get_classes
from egsim.management.commands import oq2db, reg2db, gsimsel2db, emptydb

# ============================================================================#
# !!IMPORTANT !!!
# TO ADD NEW SUBCOMMANDS import the command module and add it to this list:
# ============================================================================#
_SUBCOMMAND_MODULES = [emptydb, oq2db, reg2db, gsimsel2db]


def _get_cmd_and_help(cmd_module):
    cmd_class = get_classes(cmd_module.__name__, EgsimBaseCommand)
    if len(cmd_class) != 1:
        raise ValueError("Module %s implements %d EgsimBaseCommand class(es),"
                         "expected 1 implementation (only)" %
                         (cmd_module, len(cmd_class)))
    cmd_class = list(cmd_class.values())[0]
    help_ = getattr(cmd_class, 'help', 'No doc available')
    idx = help_.find('Notes:')
    if idx > -1:
        help_ = help_[:idx]
    cmd_name = cmd_module.__name__.split('.')[-1]  # the module name (no path)
    return {'name': cmd_name, 'cmd': cmd_class, 'help': help_}


SUBCOMMANDS = [_get_cmd_and_help(_) for _ in _SUBCOMMAND_MODULES]


class Command(EgsimBaseCommand):
    """Class implementing the command functionality"""

    # As help, use the module docstring (until the first empty line):
    help = globals()['__doc__'].split("\n\n")[0]
    # then add the subcommands help
    help += "\n".join([
        '\nThis command calls in series all the following (sub)commands:',
        "\n\n".join("\n%s\n%s\n%s" % (_['name'], '='*len(_['name']), _['help'])
                    for _ in SUBCOMMANDS)
    ])

    # help = "\n". join([
    #     'Initializes and populates the database with all eGSIM required data.',
    #     'This is also the RECOMMENDED command to be executed every time eGSIM',
    #     'should be updated with new external source data or a new OpenQuake ',
    #     'version. See the README file in this directory for details.',
    #     'This command calls in series all the following (sub)commands:',
    #     "\n\n".join("\n%s\n%s\n%s" % (_['name'], '='*len(_['name']), _['help'])
    #                 for _ in SUBCOMMANDS),
    #     '\nNotes:',
    #     ' - GSIM: Ground Shaking Intensity Model',
    #     ' - IMT: Intensity Measure Type',
    #     ' - TRT: Tectonic Region Type',
    #     ' - All database tables will be emptied and rewritten'
    # ])

    #     def add_arguments(self, parser):
    #         parser.add_argument('poll_id', nargs='+', type=int)

    def handle(self, *args, **options):
        """executes the command"""

        # set options['interactive'] as True by default (see `emptydb` command)
        options.setdefault('interactive', True)

        for cmd in SUBCOMMANDS:
            # The function below (from django.core.management):
            # call_command(cmd, stdout=self.stdout, stderr=self.stderr,
            #             **options)
            # is a wrapper around Command.execute(*args, **options)
            # thus we call the latter (also to import explicitly the used
            # commands
            cmd_obj = cmd['cmd_class'](stdout=self.stdout, stderr=self.stderr)
            # cmd_obj arguments like no_color and force_color are left as default:
            cmd_obj.execute(*args, **options)
