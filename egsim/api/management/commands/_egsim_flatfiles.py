"""
Created on 11 Apr 2019

@author: riccardo
"""
import os
from os.path import join, isdir, abspath, dirname, isfile, basename, splitext

from django.core.management.base import CommandError

from . import EgsimBaseCommand
from ..flatfile_parsers import EsmFlatfileParser
from ... import models

SRC_DIR = EgsimBaseCommand.data_path('predefined_flatfiles')

DEST_DIR = models.Flatfile.BASEDIR_PATH


class Command(EgsimBaseCommand):
    """Command to convert predefined flatfiles (usually in CSV format) into HDF
    files suitable for the eGSIM API
    """

    # flatfiles abs paths (csv or zipped csv) -> :class:`FlatfileParser`:
    PARSERS = {
        join(SRC_DIR, "ESM_flatfile_2018_SA.csv.zip"): EsmFlatfileParser
    }

    help = ('Parse predefined flatfile(s) from the "commands/data" directory into '
            'flatfiles in HDF format suitable for residuals computation in eGSIM. '
            'The HDF flatfiles will be stored in: "{models.Flatfile.BASEDIR_PATH}"')

    def handle(self, *args, **options):
        """Parse each pre-defined flatfile"""

        self.printinfo('Creating pre-defined Flatfiles and storing their '
                       'metadata to DB:')
        self.empty_db_table(models.Flatfile)

        destdir = DEST_DIR
        if not isdir(destdir):
            if isdir(dirname(destdir)):
                self.printinfo(f'Creating directory {destdir}')
                os.makedirs(destdir)
            if not isdir(destdir):
                raise CommandError(f"'{destdir}' does not exist and could not "
                                   f"be created. NOTE: In DEBUG mode, the parent "
                                   f"directory should be git-ignored")

        parsers = {}
        for fullpath, parser in self.PARSERS.items():
            if not isfile(fullpath):
                raise CommandError(f'File does not exist: "{fullpath}".\nPlease '
                                   f'check `{__name__}.{__class__.__name__}.PARSERS`')
            parsers[fullpath] = parser

        numfiles = 0
        for filepath, parser in parsers.items():
            dfr = parser.parse(filepath)
            data_source = self.data_source(filepath)
            # ff name: use str.split to remove all extensions (e.g. ".csv.zip"):
            name = data_source.get('name', basename(filepath).split(".")[0])
            data_source.setdefault('name', name)
            destfile = abspath(join(destdir, name + '.hdf'))
            self.printinfo(f' - Saving flatfile to "{destfile}"')
            dfr.to_hdf(destfile, key=name, format='table', mode='w')
            numfiles += 1
            models.Flatfile.objects.create(**data_source, expiration=None,
                                           hidden=False, filepath=destfile)

        self.printsuccess(f'{numfiles} models created in "{destdir}"')
