'''
Created on 11 Apr 2019

@author: riccardo
'''

import os
from stat import S_IREAD, S_IRGRP, S_IROTH
from tempfile import NamedTemporaryFile

from django.core.management.base import BaseCommand, CommandError
# from django.conf import settings

from smtk.sm_table import GMTableParser
from egsim.core.utils import get_gmdb_path, get_gmdb_names


# define here the default user defined GMTableParser
# (must be on the top of this module).
# FIXME: should be implemented in smtk
class UserDefinedTableParser(GMTableParser):
    '''defines the standard default table parser.
    FIXME: should be probably done in smtk. Just implement the method
    below in GMTableParser (why wasn't it done?)
    '''

    @classmethod
    def get_sa_columns(cls, csv_fieldnames):
        """
        Checks for all column names in `csv_fieldnames` with the format
        "SA_<period>" and returns a dict of them mapped to their numeric
        period.

        (from super-doc):

        This class will then sort and save SA periods accordingly.
        You can also implement here operations which should be executed once
        at the beginning of the flatfile parsing, such as e.g.
        creating objects and storing them as class attributes later accessible
        in :method:`parse_row`

        :param csv_fieldnames: an iterable of strings representing the
            header of the persed csv file
        """
        vals = {}
        for _ in csv_fieldnames:
            if _[:3].upper() == 'SA_':
                try:
                    vals[_] = float(_[3:])
                except (TypeError, ValueError):
                    raise ValueError(f'column name error "{_}": '
                                     f'"{_[3:]}" must be numeric')
        if not vals:
            raise ValueError('No "SA" column found (format must be: '
                             'SA_<period>, e.g. SA_0.1)')
        return vals


class Command(BaseCommand):
    '''Command to create a standard Ground Motion Database
    '''
    help = ('Creates a Ground Motion Database from a provided CSV flatfile(s). '
            'as arguments. The fields of the flatfile(s) must match those '
            'provided in smtk.GMTableParser. '
            'The database name will be the file name, without extension')

    parserclass = UserDefinedTableParser  # see below

    @property
    def outpath(self):
        '''Returns the directory where to write all HDF files'''
        return get_gmdb_path()

    @staticmethod
    def existingdir(fpath, prompt=True):
        if not os.path.isdir(fpath) and prompt:
            res = input('Output directory "%s" does not exist. '
                        'Create it? y=Yes, '
                        'anything else=exit\n' % str(fpath))
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
        '''Adds arguments to the command'''
        # https://docs.python.org/3/library/argparse.html#nargs
        parser.add_argument('flatfile', nargs='+', help='Flatfile path')
        parser.add_argument('--sep', nargs='?', default='semicolon',
                            help=('The csv separator. '
                                  'Can be (without quotes): '
                                  'semicolon, comma, space, tab. '
                                  'Defaults to semicolon'))

    def handle(self, *args, **options):
        '''parses each passed flatfile (as simple command line argument):
            ```
            python manage.py gmdb file1.csv file2.csv
            ```
            and writes them as file1.hdf5, file2.hdf5 in `self.outpath`,
            which is usually some directory specified in the Django settings
            file (e.g. the MEDIA_ROOT or some subfolder)

            Note that an HDF5 file can store several flatfiles in the
            form of an HDF5 table (one table = one Ground Motion databases,
            gmdb). This command creates one HDF5 file with one gmdb per
            flatfile, for three reasons:
            1. In case of errors or maintainence tasks, we do not have to
               recreate all gmdb but only those we need to
            2. It is easier to know which gmdb we have and their name
               by simply looking at the files within `self.outpath`
            3. In principle, all HDF5 files are intended to be only read and
               not modified, so there shouldn't be concurrency problems.
               However, avoiding concurrent access to the same file when
               possible is surely not a hindrances
            Note that if in the future we want to merge all files into a single
            one, we have to change the code here only: egsim is not expecting
            a single table per HDF5 file. See `get_gmdb_names`
            and `get_gmdb_path` in `utils.py` for details
        '''
        try:
            # assure outdir exists, raises if unable to create the dir
            # (the user will be prompted in case):
            outdir = self.existingdir(self.outpath)
            input_paths = options['flatfile']
            # check that all files exist HERE because it is annoying raising
            # e.g., at the 3rd flatfile after several minutes of processing
            for _ in input_paths:
                if not os.path.isfile(_):
                    raise ValueError(f'"{_}" is not an existing file')
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

            delimiter = {
                'semicolon': ';',
                'comma': ',',
                'space': ' ',
                'tab': '\t'
            }[options['sep']]

            for dbname, fle in flatfiles.items():
                self.stdout.write('Parsing "%s"' % fle)
                # FIXME: remove this 'trycatch' statement, see _create_bom_free
                fle2 = None
                try:
                    fle2 = _create_bom_free_flatfile(fle)
                    outpath = os.path.join(outdir, dbname + ".hdf5")
                    stats = self.parserclass.parse(fle2, outpath, dbname,
                                                   delimiter=delimiter)
                    self.stdout.write(self.style.SUCCESS('Created "%s" in "%s"'
                                                         % (dbname, outpath)))
                    self.stdout.write(self.style.SUCCESS('Stats: "%s"'
                                                         % str(stats)))
                    # set HDF5 file write protected
                    # (https://stackoverflow.com/a/28492823):
                    os.chmod(outpath, S_IREAD | S_IRGRP | S_IROTH)
                    self.stdout.write('')
                finally:
                    if fle2 is not None and os.path.isfile(fle2):
                        os.unlink(fle2)
                    if fle2 is not None and os.path.isfile(fle2):
                        self.style.WARNING(f'WARNING: Unable to delete '
                                           f'temporary file "{fle2}"')
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(f'{str(type(exc))}: {str(exc)}')


def _create_bom_free_flatfile(flatfile_path):
    """Creates a BOM free copy of the given flatfile and returns it.
    If the flatfile content has no BOM, an exact copy of it is returned.
    A BOM is a character (which
    might be put there by softwares like Excel when exporting) that dictates
    the CSV encoding and should not be read as part of the CSV data.

    For info see:
    https://stackoverflow.com/a/49150749

    FIXME: The solution here is quite hacky as a new file is created.
    A cleaner and simpler fix would be getting rid of this
    function (using a normal 'open') and setting
    kwargs['encoding']= 'utf-8-sig' in the method
    `GMTableParser._get_csv_reader` of the smtk package

    Returns:
        the path of the copy of the flatfile, without BOM
    """
    with NamedTemporaryFile(mode='w', suffix='.csv', encoding='utf-8',
                            delete=False) as _out_:
        with open(flatfile_path, mode='r', encoding='utf-8-sig') as _in_:
            _out_.write(_in_.read())
        return _out_.name
