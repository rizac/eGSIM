"""
Created on 11 Apr 2019

@author: riccardo
"""
import os
from os.path import join, isdir, abspath, dirname, isfile

from django.core.management.base import CommandError
from django.conf import settings

from egsim import models
from egsim.management.commands import EgsimBaseCommand
from egsim.management.flatfile_parsers import EsmFlatfileParser


class Command(EgsimBaseCommand):
    """Command to convert predefined flatfiles (usually in CSV format) into HDF
    files suitable for the eGSIM API
    """

    # dict of source file names (CSV , zip) and relative :class:`FlatfileParser`
    # (see :meth:`src_dir` for details)
    PARSERS = {
        "ESM_flatfile_2018_SA.csv.zip": EsmFlatfileParser
    }

    # Source and destination directory name (see `src_dir` and `dest_dir` for details)
    dir_name = 'predefined_flatfiles'

    @classmethod
    def src_dir(cls):
        """Return the source directory by joining the commands `data` directory
        (:meth:`EgsimBasecommand.data_dir`) and  `dir_name`. All keys of PARSERS
        must be files in the returned directory
        """
        return cls.data_dir(cls.dir_name)

    @classmethod
    def dest_dir(cls):
        """Return the source directory by joining the [media] directory configured
         in the current settings and  `dir_name`. All flatfiles in HDF format will be
         stored in the in the returned directory
        """
        return abspath(join(settings.MEDIA_ROOT, cls.dir_name))

    help = ('Convert predefined flatfile(s) inside the "commands/data" directory '
            'into HDF tables for usage within eGSIM. The tables will be stored in the '
            f'directory "[media]/{dir_name}", where [media] is the media '
            'directory configured in the current Django settings')

    def handle(self, *args, **options):
        """Parse each pre-defined flatfile"""

        self.printinfo('Creating pre-defined Flatfiles and storing their '
                       'metadata to DB:')
        self.empty_db_table(models.Flatfile)

        destdir = self.dest_dir()
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

        parsers = {}
        for filename, parser in self.PARSERS.items():
            fullpath = join(self.src_dir(), filename)
            if not isfile(fullpath):
                raise CommandError(f'File does not exist: "{fullpath}".\nPlease '
                                   f'check `{__name__}.{__class__.__name__}.PARSERS`')
            parsers[fullpath] = parser

        numfiles = 0
        for filepath, parser in parsers.items():
            dfr = parser.parse(filepath)
            destfile = join(destdir, parser.NAME + '.hdf')
            self.printinfo(f' - Saving flatfile to "{destfile}"')
            dfr.to_hdf(destfile, key=parser.NAME, format='table', mode='a')
            numfiles += 1
            models.Flatfile.objects.create(name=parser.NAME,
                                           url=parser.URL,
                                           description=parser.DESCRIPTION,
                                           path=destfile)

        self.printsuccess(f'{numfiles} models created in "{destdir}"')
