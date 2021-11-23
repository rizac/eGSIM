"""
Created on 11 Apr 2019

@author: riccardo
"""
import inspect
import os
from os.path import join, isdir, abspath, dirname

from django.core.management.base import CommandError
from django.conf import settings

from egsim import models
from egsim.management.commands import EgsimBaseCommand, _flatfile_parsers


class Command(EgsimBaseCommand):
    """Command to convert predefined flatfiles (usually in CSV format) into HDF
    files suitable for the eGSIM API
    """

    dest_dir_name = 'predefined_flatfiles'  # where flatfiles (HDF) will be stored

    @classmethod
    def dest_dir(cls):
        return abspath(join(settings.MEDIA_ROOT, cls.dest_dir_name))

    help = ('Convert predefined flatfile(s) inside the "commands/data" directory '
            'into HDF tables for usage within eGSIM. The tables will be stored in the '
            f'directory "[media]/{dest_dir_name}", where [media] is the media '
            'directory configured in the current Django settings')

    def handle(self, *args, **options):
        """Parse each pre-defined flatfile"""

        self.printinfo('Creating pre-defined Flatfiles and storing their '
                       'metadata to DB:')
        self.empty_db_table(models.Flatfile)

        destdir = abspath(join(settings.MEDIA_ROOT, self.dest_dir_name))
        if not isdir(destdir):
            if isdir(dirname(destdir)):
                self.printinfo(f'Creating directory {destdir}')
                os.makedirs(destdir)
            if not isdir(destdir):
                raise CommandError(f"'{destdir}' does not exist and could not "
                                   f"be created. NOTE: In DEBUG mode, the parent "
                                   f"directory should be git-ignored")
        elif len(os.listdir(destdir)):
            raise CommandError(f"'{destdir}' is not empty: remove all its content "
                               f"manually and restart the process")

        parsers = find_subclasses(_flatfile_parsers, _flatfile_parsers.FlatfileParser)

        numfiles = 0
        for parser in parsers:
            dfr = parser.get_dataframe()
            destfile = join(destdir, parser.NAME + '.hdf')
            self.printinfo(f' - Saving flatfile to "{destfile}"')
            dfr.to_hdf(destfile, key=parser.NAME, format='table', mode='a')
            numfiles += 1
            models.Flatfile.objects.create(name=parser.NAME,
                                           url=parser.URL,
                                           description=parser.DESCRIPTION,
                                           path=destfile)

        self.printsuccess(f'{numfiles} models created in "{destdir}"')


def find_subclasses(module, base_class, include_base=False):
    return [
        cls for name, cls in inspect.getmembers(module)
        if inspect.isclass(cls) and issubclass(cls, base_class) and
               (include_base or cls != base_class)
    ]