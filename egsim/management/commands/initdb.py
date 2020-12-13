"""
Module for initalizing the databse with all required input data from external
sources

For info see:
https://django.readthedocs.io/en/2.0.x/howto/custom-management-commands.html

Created on 6 Apr 2019

@author: riccardo
"""

from django.db.utils import OperationalError
from django.core.management.base import BaseCommand, CommandError

from egsim.models import empty_all
from ._utils import EgsimBaseCommand, get_classes
from egsim.management.commands import oq2db, reg2db, gsimsel2db


# TO ADD NEW SUBCOMMANDS import the command module and add it to this list:
_SUBCOMMAND_MODULES = [oq2db, reg2db, gsimsel2db]


def _get_cmd_and_help(cmd_module):
    cmd_class = get_classes(cmd_module.__name__, EgsimBaseCommand)
    if len(cmd_class) != 1:
        raise ValueError("Module %s implements %d EgsimBaseCommand class(es),"
                         "exepcted 1 implementation (only)" %
                         (cmd_module, len(cmd_class)))
    cmd_class = list(cmd_class.values())[0]
    help_ = getattr(cmd_class, 'help', 'No doc available')
    idx = help_.find('Note:')
    if idx > -1:
        help_ = help_[:idx]
    cmd_name = cmd_module.__name__.split('.')[-1]  # the module name (no path)
    return {'name': cmd_name, 'cmd': cmd_class, 'help': help_}


SUBCOMMANDS = [_get_cmd_and_help(_) for _ in _SUBCOMMAND_MODULES]


class Command(EgsimBaseCommand):
    """Command to initialize the db:
    ```
    export DJANGO_SETTINGS_MODULE="..."; python manage.py initdb
    ```
    """
    help = ('Initializes and populates the database with all eGSIM required '
            'data.\nCalls in series all the following (sub)commands:\n') +\
            "\n\n".join("\n%s\n%s" % (_['name'], _['help'])
                        for _ in SUBCOMMANDS)

    #     def add_arguments(self, parser):
    #         parser.add_argument('poll_id', nargs='+', type=int)

    def handle(self, *args, **options):

        # delete db:
        try:
            self.printinfo('Emptying DB Tables')
            empty_all()
        except OperationalError as no_db:
            raise CommandError('%s.\nDid you create the db first?\n(for '
                               'info see: https://docs.djangoproject.'
                               'com/en/2.2/topics/migrations/#workflow)' %
                               str(no_db))

        for cmd in SUBCOMMANDS:
            # The function below (from django.core.management):
            # call_command(cmd, stdout=self.stdout, stderr=self.stderr,
            #             **options)
            # is a wrapper around Command.execute(*args, **options)
            # thus we call the lateter (also to import explicitly the used
            # commands
            cmd_obj = cmd['cmd_class'](stdout=self.stdout, stderr=self.stderr)
            # cmd_obj arguments like no_color and force_color are set as default
            # meaning that
            cmd_obj.execute(*args, **options)
