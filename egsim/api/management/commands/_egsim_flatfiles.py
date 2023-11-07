"""
Parse predefined flatfile(s) from the "commands/data" directory into
flatfiles in HDF format suitable for residuals computation in eGSIM.
The HDF flatfiles will be stored in: "{models.Flatfile.BASEDIR_PATH}"

Created on 11 Apr 2019

@author: riccardo
"""
from os.path import join, abspath

from egsim.smtk.flatfile.columns import load_from_yaml
from egsim.smtk.registry import registered_imts
from . import EgsimBaseCommand
from ... import models
from ...data.flatfiles import get_flatfiles, DATA


class Command(EgsimBaseCommand):
    """Command to convert predefined flatfiles (usually in CSV format) into HDF
    files suitable for the eGSIM API
    """

    # As help, use the module docstring (until the first empty line):
    help = globals()['__doc__'].split("\n\n")[0]

    def handle(self, *args, **options):
        """Parse each pre-defined flatfile"""

        self.printinfo('Parsing Flatfiles from sources:')
        self.empty_db_table(models.Flatfile)

        destdir = self.output_dir('flatfiles')
        ffcolumns = set(load_from_yaml())
        imts = set(registered_imts)
        numfiles = 0
        for name, dfr in get_flatfiles():
            ref = DATA.get(name, {})
            # ff name: use str.split to remove all extensions (e.g. ".csv.zip"):
            ref['name'] = name
            destfile = abspath(join(destdir, name + '.hdf'))
            dfr.to_hdf(destfile, key=name, format='table', mode='w')
            numfiles += 1
            self.printinfo(f'  Flatfile "{name}" ({destfile})')
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
            self.printinfo(info_str)
            if unknown_cols:
                self.printinfo(f"   {', '.join(sorted(unknown_cols))}")
            # store flatfile refs, if any:
            ref_keys = set(DATA.get(name, {})) & \
                set(f.name for f in models.Citable._meta.get_fields())  # noqa
            refs = {f : DATA[name][f] for f in ref_keys}
            models.Flatfile.objects.create(name=name, filepath=destfile, **refs)

        self.printsuccess(f'{numfiles} flatfile(s) saved to {destdir}')

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

