"""
Empties and (re)populate the database with all eGSIM required data.
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

@author: riccardo
"""
from django.core.management import call_command, load_command_class

from ._utils import EgsimBaseCommand

# ===============#============================================================#
# !!IMPORTANT !!! TO ADD NEW SUBCOMMANDS add its name here below:
# ============================================================================#
_SUBCOMMAND_MODULES = ['egsim_flush', '_egsim_oq', 'egsim_reg', 'egsim_sel']

APPNAME = 'egsim'
SUBCOMMANDS = [load_command_class(APPNAME, _) for _ in _SUBCOMMAND_MODULES]


class Command(EgsimBaseCommand):
    """Class implementing the command functionality"""

    # As help, use the module docstring (until the first empty line):
    help = globals()['__doc__'].split("\n\n")[0]
    # then add the subcommands help
    help += "\n".join([
        '\nThis command performs in series the following operations:',
        "\n\n".join(cmd.help for cmd in SUBCOMMANDS)
    ])

    #     def add_arguments(self, parser):
    #         parser.add_argument('poll_id', nargs='+', type=int)

    def handle(self, *args, **options):
        """executes the command"""

        # set options['interactive'] as True by default (see `emptydb` command)
        options.setdefault('interactive', True)

        for cmd in SUBCOMMANDS:
            call_command(cmd, *args, **options)
