"""
eGSIM management command. See `Command.help` for details
"""
import warnings

from django.core.management import CommandError, BaseCommand

from egsim.smtk import registered_gsims, InvalidInput, gsim
from ... import models


class Command(BaseCommand):
    """Class implementing the command functionality"""

    # As help, use the module docstring (until the first empty line):
    help = """Populate the Database with all valid OpenQuake models"""

    def handle(self, *args, **options):
        """Executes the command

        :param args: positional arguments (?). Unclear what should be given
            here. Django doc and Google did not provide much help, source code
            inspection suggests it is here for legacy code (OptParse)
        :param options: any argument (optional or positional), accessible
            as options[<paramname>]. For info see:
            https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/
        """
        self.stdout.write('Populating the database with OpenQuake models')
        models.Gsim.objects.all().delete()
        if models.Gsim.objects.all().count():
            raise CommandError('Table is not empty (deletion failed?), check the DB')
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
        self.stdout.write(self.style.SUCCESS(f'Models saved: {ok}, '
                                             f'discarded: {discarded}'))


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