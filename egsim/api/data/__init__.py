import shutil
from collections.abc import Iterable
from os import makedirs
from os.path import join, dirname, relpath, isdir, basename
import json
import sys
from typing import Union

from egsim.api.data.flatfiles import get_flatfiles
from egsim.api.data.flatfiles.parsers import esm2018
from egsim.smtk import registered_imts
from egsim.smtk.flatfile import _load_flatfile_metadata

refs_file_path = join(dirname(__file__), "refs.json")
refs = json.load(refs_file_path)


def parse_flatfiles(srcdir: str, destdir: str,
                    stdout=sys.stdout):  # src_dir= Nextcloud_dir/flatfiles dest_dir=media file/faltfile, stdout = slf.stdout
    """Parse each pre-defined flatfile"""
    PARSERS = {
        join(srcdir, "ESM_flatfile_2018_SA.csv.zip"): esm2018.parse,
        join(srcdir, "kik2024_SA.h5.zip"): esm2018.parse,
        join(srcdir, "knet2024_SA.h5.zip"): esm2018.parse,
    }

    stdout.write('Parsing Flatfiles from sources:')

    ffcolumns = set(_load_flatfile_metadata())
    imts = set(registered_imts)
    for srcpath, parser in PARSERS:
        ff_ref = refs[relpath(srcpath, refs_file_path)]
        dfr = parser(srcpath)
        # save object metadata to db:
        name = ff_ref['name']
        destpath = join(destdir, name) + '.hdf'
        write_flatfile(dfr, destpath, key=name)

        # store object refs, if any:
        stdout.write(f'  Flatfile "{name}" ({destpath})')
        # print some stats:
        cols, metadata_cols, imt_cols_no_sa, imt_cols_sa, unknown_cols = \
            get_flatfile_stats(dfr, ffcolumns, imts)
        info_str = (f'    Columns: {len(cols)} total, '
                    f'{len(metadata_cols)} metadata, '
                    f'{len(imt_cols_no_sa) + len(imt_cols_sa)} IMTs '
                    f'({len(imt_cols_sa)} SA periods), '
                    f'{len(unknown_cols)} user-defined')
        if unknown_cols:
            info_str += ":"
        stdout.write(info_str)
        if unknown_cols:
            stdout.write(f"   {', '.join(sorted(unknown_cols))}")

        yield ff_ref | {'filepath': destpath}


def write_flatfile(flatfile, filepath: str, mkdirs=True, **kwargs):
    """Write this instance media file as HDF file on disk

    @param flatfile: a pandas DataFrame denoting a **valid** flatfile (no check
        or validation will be performed)
    @param filepath: the destination path (absolute path)
    @param mkdirs: recursively create the parent directory of `self.filepath` if
        non-existing
    @param kwargs: additional arguments to pandas `to_hdf` ('format', 'mode'
        and 'key' will be set in this function if not given)
    """
    if mkdirs and not isdir(dirname(filepath)):
        makedirs(dirname(filepath))
    kwargs.setdefault('format', 'table')
    kwargs.setdefault('mode', 'w')
    kwargs.setdefault('key', "flatfile")
    flatfile.to_hdf(filepath, **kwargs)


def get_flatfile_stats(flatfile_dataframe, db_ff_columns: set[str], db_imts: set[str]):
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


def copy_regionalizations(srcdir: str, destdir: str,
                          stdout=sys.stdout):  # src_dir= Nextcloud_dir/flatfiles dest_dir=media file/faltfile, stdout = slf.stdout
    """Copy each pre-defined regionalizations"""

    stdout.write('Copying Regionalizations from sources:')

    FILES = [
        join(srcdir, "global_stable.geo.json"),
        join(srcdir, "global_volcanic.geo.json"),
        join(srcdir, "share.geo.json"),
        join(srcdir, "eshm20.geo.json"),
        join(srcdir, "germany.geo.json"),
    ]

    # warnings.simplefilter("ignore")
    for srcpath in FILES:
        # save object metadata to db:
        reg_ref = refs[relpath(srcpath, refs_file_path)]
        name = reg_ref['name']
        destpath = join(destdir, name + ".geo.json")
        shutil.copy2(srcpath, destpath)

        with open(destpath, 'r') as _:
            jdict = json.load(_)
            regions = jdict['features']
            stdout.write(f'  Regionalization "{name}" ({destpath}), '
                         f'{len(regions)} region(s) (geoJSON features):')
            for feat in regions:
                stdout.write(f"    {feat['properties']['region']}: "
                             f"{len(feat['properties']['models'])} model(s), "
                             f"geometry type: {feat['geometry']['type']}")

        yield reg_ref | {'filepath': destpath}

# 1. Temporarily make a public link of the folder you want to copy. You can do it on the browser, or in macos finder right click -> Nextcloud -> share) to create a public link. The public link will be something like https://nextcloud.gfz.de/s/SHoUdmN4YYyrTJq
#
# 2. Go on the server and type (note the /download added at the end of the source url):
#
# wget https://nextcloud.gfz.de/s/SHoUdmN4YYyrTJq/download -O [DEST_ZIP_FILE_PATH]
#
# 3. Unzip the content
#
# unzip [DEST_ZIP_FILE_PATH] -d /path/to/destination/
#
#
# 4. Unshare the content: go to finder (or the browser) and do the same procedure as in 1, but click on "unshare" (or similar)
