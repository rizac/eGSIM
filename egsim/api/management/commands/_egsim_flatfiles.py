"""
eGSIM management command. See `Command.help` for details
"""
from os.path import join

from django.core.management import BaseCommand, CommandError

from egsim.smtk.flatfile import _load_flatfile_metadata  # noqa
from egsim.smtk.registry import registered_imts
from ... import models
from ...data import parse_flatfiles
from ...data.flatfiles import get_flatfiles, DATA


class Command(BaseCommand):

    help = "Parse CSV flatfiles stored in the API source data into standardized eGSIM " \
           "flatfiles. Store each parsed flatfile as HDF in the API MEDIA directory " \
           "and the flatfile metadata in the Database"

    def handle(self, *args, **options):
        """Parse each pre-defined flatfile"""
        models.Flatfile.objects.all().delete()
        if models.Flatfile.objects.all().count():
            raise CommandError('Table is not empty (deletion failed?), check the DB')

        from django.conf import settings
        numfiles = 0
        srcdir = join(settings.EGSIM_SOURCE_DATA_PATH, "flatfiles"),
        destdir = join(settings.MEDIA_ROOT, "flatfiles")
        for numfiles, ff_refs in enumerate(parse_flatfiles(
            srcdir=srcdir, destdir=destdir, stdout=self.stdout
        ), start=1):
            # store object refs, if any:
            kwargs = set(ff_refs) & \
                       set(f.name for f in models.Reference._meta.get_fields())  # noqa
            models.Flatfile.objects.create(**{k: ff_refs[k] for k in kwargs})

        self.stdout.write(self.style.SUCCESS(f'{numfiles} flatfile(s) '
                                             f'saved to {destdir}'))
