"""
eGSIM management command. See `Command.help` for details
"""
from os.path import join

from django.core.management import BaseCommand, CommandError

from egsim.smtk.flatfile import _load_flatfile_metadata
from egsim.smtk.registry import registered_imts
from ... import models
from ...data.flatfiles import get_flatfiles, DATA


class Command(BaseCommand):

    help = "Parse CSV flatfiles stored in the API source data into standardized eGSIM " \
           "flatfiles. Store each parsed flatfile as HDF in the API MEDIA directory " \
           "and the flatfile metadata in the Database"

    def handle(self, *args, **options):
        """Parse each pre-defined flatfile"""
        self.stdout.write('Parsing Flatfiles from sources:')
        models.Flatfile.objects.all().delete()
        if models.Flatfile.objects.all().count():
            raise CommandError('Table is not empty (deletion failed?), check the DB')

        destdir = 'flatfiles'
        ffcolumns = set(_load_flatfile_metadata())
        imts = set(registered_imts)
        numfiles = 0
        for name, dfr in get_flatfiles():
            # save object metadata to db:
            relpath = join(destdir, name) + '.hdf'
            # store object refs, if any:
            ref_keys = set(DATA.get(name, {})) & \
                       set(f.name for f in models.Reference._meta.get_fields())  # noqa
            refs = {f: DATA[name][f] for f in ref_keys}
            db_obj = models.Flatfile.objects.create(name=name,
                                                    media_root_path=relpath,
                                                    **refs)
            db_obj.write_to_filepath(dfr)

            numfiles += 1
            self.stdout.write(f'  Flatfile "{name}" ({db_obj.filepath})')
            # print some stats:
            cols, metadata_cols, imt_cols_no_sa, imt_cols_sa, unknown_cols = \
                self.get_stats(dfr, ffcolumns, imts)
            info_str = (f'    Columns: {len(cols)} total, '
                        f'{len(metadata_cols)} metadata, '
                        f'{len(imt_cols_no_sa) + len(imt_cols_sa)} IMTs '
                        f'({len(imt_cols_sa)} SA periods), '
                        f'{len(unknown_cols)} user-defined')
            if unknown_cols:
                info_str += ":"
            self.stdout.write(info_str)
            if unknown_cols:
                self.stdout.write(f"   {', '.join(sorted(unknown_cols))}")

        self.stdout.write(self.style.SUCCESS(f'{numfiles} flatfile(s) '
                                             f'saved to {destdir}'))

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

