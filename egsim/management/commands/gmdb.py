'''
Created on 11 Apr 2019

@author: riccardo
'''

import os
from stat import S_IREAD, S_IRGRP, S_IROTH

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from smtk.sm_table import GMTableParser
from egsim.core.utils import get_gmdb_path, get_gmdb_names


class Command(BaseCommand):
    '''Command to create a standard Ground Motion Database
    '''
    help = ('Creates a Ground Motion Database from a provided CSV flatfile(s). '
            'as arguments. The fields of the flatfile(s) must match those '
            'provided in smtk.GMTableParser, and be separated by ";"'
            'The database name will be the file name, without extension')

    parserclass = GMTableParser

    @property
    def outpath(self):
        '''Returns the directory where to write all HDF files'''
        return get_gmdb_path()

    @staticmethod
    def existingdir(fpath, prompt=True):
        if not os.path.isdir(fpath) and prompt:
            res = input('"%s" does not exist. Should I create it? y=Yes, '
                        'anything else=exit')
            if res == 'y':
                try:
                    os.makedirs(fpath)
                except:  # @IgnorePep8 pylint: disable=bare-except
                    pass
                if not os.path.isdir(fpath):
                    raise Exception('Unable to create "%s"' % fpath)
            else:
                raise Exception('Operation aborted by user')
        if not os.path.isdir(fpath):
            raise Exception('"%s" does not exist' % fpath)
        return fpath

    @property
    def dbnames(self):
        '''returns the database (table) names in the HDF file pointed by
        self.outpath'''
        return get_gmdb_names(self.outpath)

    def add_arguments(self, parser):
        parser.add_argument('flatfile', nargs='+', help='Flatfile path')

    def handle(self, *args, **options):
        '''parses each passed flatfile (as simple command line argument):
            ```
            python manage.py gmdb_esm file1.csv file2.csv
            ```
            and writes them as file1.hdf5, file2.hdf5 in `self.outpath`,
            which should be some directory specified in the Django settings
            file (usually, the MEDIA_ROOT or some subfolder)

            Note that each flatfile will generate a HDF% file with a single
            Gorund motion table (HDF group) with the same name of the file
            (without extension). Although the smtk GroundMotionDatabase was
            designed to have each flatfile as a table of a HDF5 Group
            (= HDF5 directory) of a single HDF file, we create one Hdf5 file
            per flatfile for three reasons:
            1. In case of errors or maintainence tasks, we do not have to
               recreate all flatfiles but only those we need to
            2. It is easier to know which Gm database we have and their name
               by simply looking at the files within `self.outpath`
            3. In principle, all Gmdb HDF5 files are read-only, so there
               should not be a problem in concurrent access. However, avoiding
               concurrent access to the same file when possible is surely not
               a hindrances
            Note that if in the future we want to merge all files into a single
            one, egsim is already capable of doing that. See `get_gmdb_names`
            and `get_gmdb_path` in `utils.py` for details
        '''
        try:
            # assure outdir exists, raises if unable to create the dir
            # (the user will be prompted in case):
            outdir = self.existingdir(self.outpath)
            input_paths = options['flatfile']
            # check that all files exist HERE because it is annoying raising
            # e.g., at the 3rd flatfile after several minutes of processing
            if any(not os.path.isfile(_) for _ in input_paths):
                raise ValueError('"%s" is not an existing file')
            # do not allow duplicate names (maybe typos?)
            if len(set(input_paths)) < len(input_paths):
                raise ValueError('Duplicated arguments: looks like some '
                                 'flatfile is specified more than once. '
                                 'Please check')

            dbnames = self.dbnames  # dict of items: dbname -> db HDF5 file
            flatfiles = {}  # dict of items: dbname -> db CSV flat file
            for fle in input_paths:
                dbname = os.path.splitext(os.path.basename(fle))[0]
                if dbname in dbnames:
                    self.stdout.write(self.style.ERROR('Database name "%s" '
                                                       'already exists'))
                    continue
                flatfiles[dbname] = fle

            if not flatfiles:
                raise Exception('No flatfile to parse')

            for dbname, fle in flatfiles.items():
                self.stdout.write('Parsing "%s"' % fle)
                outpath = os.path.join(outdir, dbname + ".hdf5")
                stats = self.parserclass.parse(fle, outpath, dbname)
                self.stdout.write(self.style.SUCCESS('Created "%s" in "%s"'
                                                     % (dbname, outpath)))
                self.stdout.write(self.style.SUCCESS('Stats: "%s"'
                                                     % str(stats)))
                # set HDF5 file write protected
                # (https://stackoverflow.com/a/28492823):
                os.chmod(outpath, S_IREAD | S_IRGRP | S_IROTH)
                self.stdout.write('')

        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(exc)