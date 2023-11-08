"""
Populate the eGSIM database with all OpenQuake data

This command is invoked by `egsim_init.py` and is currently hidden from Django
(because of the leading underscore in the module name)

Created on 6 Apr 2019

@author: riccardo z. (rizac@github.com)
"""
import warnings

from django.core.management import CommandError

from egsim.smtk import registered_gsims, InvalidInput, gsim
from . import EgsimBaseCommand
from ... import models


class Command(EgsimBaseCommand):
    """Class implementing the command functionality"""

    # As help, use the module docstring (until the first empty line):
    help = globals()['__doc__'].split("\n\n")[0]

    def handle(self, *args, **options):
        """Executes the command

        :param args: positional arguments (?). Unclear what should be given
            here. Django doc and Google did not provide much help, source code
            inspection suggests it is here for legacy code (OptParse)
        :param options: any argument (optional or positional), accessible
            as options[<paramname>]. For info see:
            https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/
        """
        # populate db:
        self.printinfo('Populating the database with OpenQuake models')
        ok = 0
        with warnings.catch_warnings():
            for name, model_cls in registered_gsims.items():
                if model_cls.superseded_by:
                    continue
                if model_cls.experimental or model_cls.non_verified or \
                        model_cls.adapted:
                    warnings.simplefilter('ignore')
                else:
                    warnings.simplefilter('error')

                # try to see if we can initialize it:
                ok += write_model(name, model_cls)

        discarded = len(registered_gsims) - ok
        self.printsuccess(f'Models saved: {ok}, discarded: {discarded}')


def write_model(name, cls):
    try:
        _ = gsim(name)  # check we can initialize the model
        models.Gsim.objects.create(
            name=name,
            unverified=cls.non_verified,
            adapted=cls.adapted,
            experimental=cls.experimental)
    except InvalidInput:
        return False
    return True