"""
Created on 16 Feb 2018

@author: riccardo
"""
from datetime import datetime
import re

from egsim.smtk.flatfile import (read_flatfile,
                                 read_registered_flatfile_columns_metadata,
                                 ColumnDtype)


def test_read_flatifle_yanml():
    flatfile_cols = read_registered_flatfile_columns_metadata()
    assert 'vs30' in flatfile_cols and 'rx' in flatfile_cols and \
           'rake' in flatfile_cols

def test_flatfile_turkey(testdata):
    fpath = testdata.path('Turkey_20230206_flatfile_geometric_mean.csv')
    dfr = read_flatfile(fpath)
    asd = 9
    # in EGSIM flatfile definition and not in Turkey flatfile:
    # {'fpeak', 'azimuth', 'station_latitude', 'station_longitude'}
    # In Turkey flatfile and not in eGSIM flatfile definition (excluding PGA, PGV, and SA):
    # {'gc2t', 'gc2u', 'sta', 'depth_bottom_of_rupture', 'event_id', 'gmid', 'longest_period', 'event_time'}


def test_get_flatfile_columndtype_get():
    import pandas as pd
    d = pd.DataFrame({
        'a': ['', None],
        'b': [datetime.utcnow(), None],
        'e': [1, 0],
        'f': [1.1, None],
    })
    for c in d.columns:
        d[c + 'categ'] = d[c].astype('category')

    for c in d.columns:
        assert ColumnDtype.get(d[c]) is not None
        assert ColumnDtype.get(d[c].values) is not None
        assert ColumnDtype.get(d[c].values[0]) is not None

    assert ColumnDtype.get(None) is None
    assert ColumnDtype.get(re.compile('')) is None

    asd = 9