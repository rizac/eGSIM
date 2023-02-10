"""
Parse predefined flatfile(s) from the "commands/data" directory into
flatfiles in HDF format suitable for residuals computation in eGSIM.
The HDF flatfiles will be stored in: "{models.Flatfile.BASEDIR_PATH}"

Created on 11 Apr 2019

@author: riccardo
"""
from typing import Sequence

import os
from os.path import join, isdir, abspath, dirname, isfile, basename, splitext

from django.core.management.base import CommandError

from . import EgsimBaseCommand
from ._egsim_oq import read_registered_flatfile_columns
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

    # As help, use the module docstring (until the first empty line):
    help = globals()['__doc__'].split("\n\n")[0]

    def handle(self, *args, **options):
        """Parse each pre-defined flatfile"""

        self.printinfo('Creating pre-defined Flatfiles and populating the database '
                       'with their metadata:')
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

        ffcolumns = set(models.FlatfileColumn.objects.only('name').
                        values_list('name', flat=True))
        imts = set(models.Imt.objects.only('name').values_list('name', flat=True))
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
            # print some stats:
            cols, metadata_cols, imt_cols_no_sa, imt_cols_sa, unknown_cols = \
                self.get_stats(dfr, ffcolumns, imts)
            info_str = (f'   Flatfile columns: {len(cols)} total, '
                        f'{len(metadata_cols)} metadata, '
                        f'{len(imt_cols_no_sa) + len(imt_cols_sa)} IMTs '
                        f'({len(imt_cols_sa)} SA), '
                        f'{len(unknown_cols)} user-defined')
            if unknown_cols:
                info_str += ":"
            self.printinfo(info_str)
            if unknown_cols:
                self.printinfo(f"   {', '.join(sorted(unknown_cols))}")
            # store flatfile metadata:
            models.Flatfile.objects.create(**data_source, expiration=None,
                                           hidden=False, filepath=destfile)

        self.printsuccess(f'{numfiles} flatfile(s) created in "{destdir}"')

    @staticmethod
    def get_stats(flatfile_dataframe, db_ff_columns: set[str], db_imts: set[str]):
        cols = set(flatfile_dataframe.columns)
        imt_cols_no_sa = cols & db_imts
        imt_cols_sa = set()
        if 'SA' in db_imts:
            imt_cols_no_sa.discard('SA')  # just in case ...
            for c in cols:
                if c.startswith('SA('):
                    imt_cols_sa.add(c)
        metadata_cols = (cols - imt_cols_no_sa - imt_cols_sa) & db_ff_columns
        unknown_cols = cols - imt_cols_no_sa - imt_cols_sa - metadata_cols
        return cols, metadata_cols, imt_cols_no_sa, imt_cols_sa, unknown_cols