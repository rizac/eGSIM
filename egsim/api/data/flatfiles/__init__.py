"""
Module for parsing CSV flatfiles into standard eGSIM flatfiles
`dict`s. See `get_flatfiles` for usage

Created on 11 Apr 2019

@author: riccardo
"""
from os.path import join, dirname
from typing import Iterable

import pandas as pd

from .parsers import esm2018


def get_flatfiles() -> Iterable[tuple[str, pd.DataFrame]]:
    """Yield tuples of `(flatfile_name, flatfile_data)`.

    :return: a tuple of the form `(flatfile_metadata, flatfile_data)`
        where the first item is a dict holding the flatfile metadata
        (e.g., URL, DOI) and has at least the key 'name' (the publicly exposed
        flatfile name), and `flatfile_data` is the flatfile data (pandas dataframe)
    """
    datadir = join(dirname(__file__), 'sources')
    data = (
        ('esm2018', join(datadir, "ESM_flatfile_2018_SA.csv.zip"), esm2018.parse),
        # join(SRC_DIR, "residual_tests_esm_data.original.csv"): EsmFlatfileParser
    )
    for name, flatfile_path, parser_function in data:
        yield name, parser_function(flatfile_path)


REFS = {
    'esm2018': {
        'display_name': "Engineering strong-motion flat-file 2018",
        'url': "https://esm-db.eu/#/products/flat_file",
        'license': "Creative Commons Attribution-NonCommercial 4.0 International "
                   "(CC BY-NC 4.0) [https://creativecommons.org/licenses/by-nc/4.0/]",
        'citation': "Lanzano G., Luzi L., Russo E., Felicetta C., D’Amico M. C., "
                    "Sgobba S., Pacor F. (2018). Engineering Strong Motion Database "
                    "(ESM) flatfile [Data set]. Istituto Nazionale di Geofisica e "
                    "Vulcanologia (INGV). https://doi.org/10.13127/esm/flatfile.1.0",
        'doi': "10.13127/esm/flatfile.1.0"
    }
}