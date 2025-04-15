"""
eGSIM management command. See `Command.help` for details
"""
from os.path import join
import warnings
from django.core.management import BaseCommand, CommandError

from ... import models
from ...data import copy_regionalizations
from ...data.regionalizations import get_regionalizations, DATA


class Command(BaseCommand):

    help = "Parse of JSON+geoJSON regionalization files stored in the API source data " \
           "into single standardized regionalization files. Store each parsed file as " \
           "JSON in the API MEDIA directory and the file metadata in the Database"

    def handle(self, *args, **options):
        """Executes the command

        :param args: positional arguments (?). Unclear what should be given
            here. Django doc and Google did not provide much help, source code
            inspection suggests it is here for legacy code (OptParse)
        :param options: any argument (optional or positional), accessible
            as options[<paramname>]. For info see:
            https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/
        """
        models.Regionalization.objects.all().delete()
        if models.Regionalization.objects.all().count():
            raise CommandError('Table is not empty (deletion failed?), check the DB')

        from django.conf import settings
        srcdir = join(settings.EGSIM_SOURCE_DATA_PATH, "flatfiles")
        destdir = join(settings.MEDIA_ROOT, "flatfiles")
        regs = 0
        for regs, reg_ref in enumerate(copy_regionalizations(
                srcdir=srcdir, destdir=destdir, stdout=self.stdout),
                start=1):
            # save object metadata to db:
            kwargs = set(reg_ref) & \
                       set(f.name for f in models.Reference._meta.get_fields())  # noqa
            models.Regionalization.objects.create(**{k: reg_ref[k] for k in kwargs})

        self.stdout.write(self.style.SUCCESS(f'{regs} regionalization(s) '
                                             f'saved to {destdir}'))
