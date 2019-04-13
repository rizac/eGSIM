'''
Created on 11 Apr 2019

@author: riccardo
'''

import os

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
    
    outpath = get_gmdb_path()

    @property
    def dbnames(self):
        '''returns the database (table) names in the HDF file pointed by
        self.outpath'''
        return get_gmdb_names(self.outpath)

    def add_arguments(self, parser):
        parser.add_argument('flatfile', nargs='+', help='Flatfile path')

    def handle(self, *args, **options):

        # delete db:
        try:
            flatfiles = []
            for fle in options['flatfile']:
                if not os.path.isfile(fle):
                    raise ValueError('"%s" is not an existing file')
                dbname = os.path.splitext(os.path.basename(fle))[0]
                if dbname in self.dbnames:
                    self.stdout.write(self.style.ERROR('Database name "%s" '
                                                       'already exists'))
                    continue
                flatfiles.append([dbname, fle])

            if not flatfiles:
                self.stdout.write('No flatfile to parse')
                return

            for dbname, fle in flatfiles:
                self.stdout.write('Parsing "%s"' % fle)
                stats = self.parserclass.parse(fle, self.outpath, dbname)
                self.stdout.write(self.style.SUCCESS('Created "%s" in "%s"'
                                                     % (dbname, self.outpath)))
                self.stdout.write(self.style.SUCCESS('Stats: "%s"'
                                                     % str(stats)))
                self.stdout.write('')

        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(exc)