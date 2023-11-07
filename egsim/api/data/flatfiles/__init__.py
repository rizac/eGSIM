"""
Module parsing CSV flatfiles in `sources` into standardized pandas DataFrame(s).
See `get_flatfiles` for usage

Created on 11 Apr 2019

@author: riccardo
"""
from os.path import join, dirname
from typing import Iterable

import pandas as pd

from .parsers import esm2018


def get_flatfiles() -> Iterable[tuple[str, pd.DataFrame]]:
    """Yield flatfiles stored in this package

    :return: a generator yielding tuples of the form `name:str, flatfile:DataFrame`
        where the first item is the flatfile name and the second
        is the `DataFrame` representing the flatfile
    """
    for name, data in DATA.items():
        yield name, data['parser'](data['sources'][0])


datadir = join(dirname(__file__), 'sources')


DATA = {
    'esm2018': {
        'sources': [join(datadir, "ESM_flatfile_2018_SA.csv.zip")],
        "parser": esm2018.parse,
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