"""egsim-init command functions"""

import shutil
from os import makedirs
from os.path import join, dirname, relpath, isdir, abspath, basename, splitext
import json
import sys
from typing import Optional

# from egsim.api.data.flatfiles import get_flatfiles
from egsim.api.data.flatfile_parsers import Esm2018, KiknetKnet
from egsim.smtk import registered_imts
from egsim.smtk.flatfile import _load_flatfile_metadata  # noqa


def parse_flatfiles(srcdir: str, destdir: str, refs_path: Optional[str] = None,
                    stdout=sys.stdout):
    """Parse each pre-defined flatfile

    :param srcdir: the source directory of the source flatfiles
        (e.g. "~/Nextcloud/flatfiles'). The usual procedure is:
        1. Add a flatfile (usually zip) in srcdir
        2. Add refs in the JSON file `refs_path`
        3. Implement a parser in a Python module
        3. Add the mapping flatfile -> parser in the body of this function
    :param destdir: the destination directory (e.g. MEDIA_ROOT/flatfiles)
    :param refs_path: the refs.json path, where all refs of the flatfiles are stored
        If missing or None, it is supposed to be next to `srcdir` and have the name
        "refs.json"
    :param stdout: the standard output to print messages
    """
    PARSERS = {
        join(srcdir, "ESM_flatfile_2018_SA.csv.zip"): Esm2018.parse,
        join(srcdir, "kik2024_SA.h5"): KiknetKnet.parse,
        join(srcdir, "knet2024_SA.h5"): KiknetKnet.parse,
    }

    if refs_path is None:
        refs_path = abspath(join(dirname(srcdir), 'refs.json'))
    with open(refs_path) as _:
        refs = json.load(_)

    stdout.write('Parsing Flatfiles from sources:')

    ffcolumns = set(_load_flatfile_metadata())
    imts = set(registered_imts)
    for srcpath, parser in PARSERS.items():
        try:
            ff_ref = refs[relpath(srcpath, dirname(refs_path))]
        except KeyError:
            raise KeyError(f'dict key "{relpath(srcpath, dirname(refs_path))}" not '
                           f'in {basename(refs_path)}')
        dfr = parser(srcpath)
        # save object metadata to db:
        name = ff_ref['name']
        destpath = join(destdir, splitext(basename(srcpath))[0]) + '.hdf'
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


def copy_regionalizations(srcdir: str, destdir: str, refs_path: Optional[str] = None,
                          stdout=sys.stdout):
    """Copy each pre-defined regionalizations

    :param srcdir: the source directory of the source flatfiles
        (e.g. "~/Nextcloud/regionalizations'). The usual procedure is:
        1. add a regionalizations (geoJSON format) in srcdir
        2. Add refs in the JSON file `refs_path`
    :param destdir: the destination directory (e.g. MEDIA_ROOT/regionalizations)
    :param refs_path: the refs.json path, where all refs of the flatfiles are stored
        If missing or None, it is supposed to be next to `srcdir` and have the name
        "refs.json"
    :param stdout: the standard output to print messages
    """
    FILES = [
        join(srcdir, "global_stable.geo.json"),
        join(srcdir, "global_volcanic.geo.json"),
        join(srcdir, "share.geo.json"),
        join(srcdir, "eshm20.geo.json"),
        join(srcdir, "germany.geo.json"),
    ]

    if refs_path is None:
        refs_path = abspath(join(dirname(srcdir), 'refs.json'))
    with open(refs_path) as _:
        refs = json.load(_)

    stdout.write('Copying Regionalizations from sources:')

    for srcpath in FILES:
        # save object metadata to db:
        try:
           reg_ref = refs[relpath(srcpath, dirname(refs_path))]
        except KeyError:
            raise KeyError(f'dict key "{relpath(srcpath, dirname(refs_path))}" not '
                           f'in {basename(refs_path)}')

        destpath = join(destdir, basename(srcpath))
        copy_regionalization(srcpath, destpath)

        with open(destpath, 'r') as _:
            jdict = json.load(_)
            regions = jdict['features']
            name = reg_ref['name']
            stdout.write(f'  Regionalization "{name}" ({destpath}), '
                         f'{len(regions)} region(s) (geoJSON features):')
            for feat in regions:
                stdout.write(f"    {feat['properties']['region']}: "
                             f"{len(feat['properties']['models'])} model(s), "
                             f"geometry type: {feat['geometry']['type']}")

        yield reg_ref | {'filepath': destpath}


def copy_regionalization(src: str, dest: str, mkdirs=True, **kwargs):
    """Write this instance media file as HDF file on disk

    @param src: source file path (geoJSON file)
    @param dest: the destination path (absolute path)
    @param mkdirs: recursively create the parent directory of `self.filepath` if
        non-existing
    @param kwargs: additional arguments to shutil.copy2
    """
    if mkdirs and not isdir(dirname(dest)):
        makedirs(dirname(dest))
    shutil.copy2(src, dest, **kwargs)

# Ad new flatfile: go to srcfolder (usually Nextcloud?)
# zip -vr destfile.zip srcfile
# Or if directory:
# zip -vr folder.zip folder/ -x "*.DS_Store"

# If on MacOs, remove entries:
# zip flatfile zip -d flatfiles/kik2024_SA.h5.zip __MACOSX/\*

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
