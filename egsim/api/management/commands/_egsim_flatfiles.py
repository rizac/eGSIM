"""
Created on 11 Apr 2019

@author: riccardo
"""
import os
from os.path import join, isdir, abspath, dirname, isfile

from django.core.management.base import CommandError
from django.conf import settings

# from egsim import models
# from egsim.management.commands import EgsimBaseCommand
# from egsim.management.flatfile_parsers import EsmFlatfileParser
from . import EgsimBaseCommand
from ..flatfile_parsers import EsmFlatfileParser
from ... import models


class Command(EgsimBaseCommand):
    """Command to convert predefined flatfiles (usually in CSV format) into HDF
    files suitable for the eGSIM API
    """

    # source flatfiles paths relative to `self.data_dir()` mapped to their
    # :class:`FlatfileParser` (files can be CSV or zipped-CSV):
    PARSERS = {
        "predefined_flatfiles/ESM_flatfile_2018_SA.csv.zip": EsmFlatfileParser
    }

    # # Source and destination directory name (see `src_dir` and `dest_dir` for details)
    # dir_name = 'predefined_flatfiles'
    #
    # @classmethod
    # def src_dir(cls):
    #     """Return the source directory by joining the commands `data` directory
    #     (:meth:`EgsimBasecommand.data_dir`) and  `dir_name`. All keys of PARSERS
    #     must be files in the returned directory
    #     """
    #     return cls.data_dir(cls.dir_name)

    help = ('Parse predefined flatfile(s) from the "commands/data" directory into '
            'flatfiles in HDF format suitable for residuals computation in eGSIM. '
            'The HDF flatfiles will be stored in: "{models.Flatfile.BASEDIR_PATH}"')

    def handle(self, *args, **options):
        """Parse each pre-defined flatfile"""

        self.printinfo('Creating pre-defined Flatfiles and storing their '
                       'metadata to DB:')
        self.empty_db_table(models.Flatfile)

        destdir = models.Flatfile.BASEDIR_PATH
        if not isdir(destdir):
            if isdir(dirname(destdir)):
                self.printinfo(f'Creating directory {destdir}')
                os.makedirs(destdir)
            if not isdir(destdir):
                raise CommandError(f"'{destdir}' does not exist and could not "
                                   f"be created. NOTE: In DEBUG mode, the parent "
                                   f"directory should be git-ignored")
        # elif len(os.listdir(destdir)):
        #     raise CommandError(f"'{destdir}' is not empty: remove all its content "
        #                        f"manually and restart the process")

        parsers = {}
        for filename, parser in self.PARSERS.items():
            fullpath = join(self.data_dir(filename))
            if not isfile(fullpath):
                raise CommandError(f'File does not exist: "{fullpath}".\nPlease '
                                   f'check `{__name__}.{__class__.__name__}.PARSERS`')
            parsers[fullpath] = parser

        numfiles = 0
        for filepath, parser in parsers.items():
            dfr = parser.parse(filepath)
            destfile = abspath(join(destdir, parser.NAME + '.hdf'))
            self.printinfo(f' - Saving flatfile to "{destfile}"')
            dfr.to_hdf(destfile, key=parser.NAME, format='table', mode='w')
            numfiles += 1
            models.Flatfile.objects.create(name=parser.NAME, url=parser.URL,
                                           expires_at=None,
                                           hidden_in_browser=False,
                                           display_name=parser.DISPLAY_NAME,
                                           path=destfile)

        self.printsuccess(f'{numfiles} models created in "{destdir}"')
