"""
Created on 16 Feb 2018

@author: riccardo
"""
import io
import pytest

from datetime import datetime
import re

import pandas as pd
from docutils.nodes import error

# import numpy as np
from egsim.smtk import flatfile
from egsim.smtk.flatfile import (read_flatfile, ColumnDtype, query)


def test_read_flatifle_yanml():
    flatfile_cols = flatfile.column_type
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


# def test_get_flatfile_columndtype_get():
#     import pandas as pd
#     d = pd.DataFrame({
#         'a': ['', None],
#         'b': [datetime.utcnow(), None],
#         'e': [1, 0],
#         'f': [1.1, None],
#     })
#     for c in d.columns:
#         d[c + 'categ'] = d[c].astype('category')
#
#     for c in d.columns:
#         assert ColumnDtype.of(d[c]) is not None
#         assert ColumnDtype.of(d[c].values) is not None
#         assert ColumnDtype.of(d[c].values[0]) is not None
#         assert ColumnDtype.of(d[c].values[0].__class__) is not None
#
#     for x  in [int, float, datetime, bool, pd.CategoricalDtype([1,2,'3'])]:
#         assert ColumnDtype.of(x) is not None
#
#     assert ColumnDtype.of(None) is None
#     assert ColumnDtype.of(re.compile('')) is None
#
#     asd = 9

from io import StringIO

def test_read_flatfile_wrong_data():

    def to_numeric(values):
        return pd.to_numeric(values, errors='coerce')

    def to_datetime(values):
        return pd.to_datetime(values, error='coerce')


    args = {
        'dtype': { "str": "str",
                  "category": pd.CategoricalDtype(['a', 'b'])},
        # 'parse_dates': ['datetime'],
        'converters': {'int': to_numeric, 'bool': to_numeric, 'datetime': to_datetime, 'float': to_numeric}
    }

    print("\nData ok")
    csv = ("int,bool,float,datetime,str,category"
           "\n"
           "1,true,1.1,2006-01-01T00:00:00,x,a"
           "\n"
           "1,true,1.1,2006-01-01T00:00:00,x,ax")
    d = pd.read_csv(StringIO(csv), **args)  # noqa
    print(d.dtypes)

    print("\nSome data empty")
    csv = ("int,bool,float,datetime,str,category"
           "\n"
           "1,true,1.1,2006-01-01T00:00:00,x,a"
           "\n"
           ",,,,"
           )
    d = pd.read_csv(StringIO(csv), **args)  # noqa
    print(d.dtypes)

    print("\nSome data empty, some wrong")
    csv = ("int,bool,float,datetime,str,category"
           "\n"
           ",,,,"
           "\n"
           "1x,1.1x,truex,2006x-05-t,e,a"
           "\n"
           "1,true,1.1,2006-01-01T00:00:00,x,x")
    d = pd.read_csv(StringIO(csv), **args)  # noqa
    print(d.dtypes)


def test_categorical():
    print()
    print(pd.read_csv(StringIO('a\nb\n1'), dtype={'a': pd.CategoricalDtype(['b', '1'])}))

    print()
    print(pd.read_csv(StringIO('a\nb\n1'), dtype={'a': 'category'}))


def test_query():
    now = datetime.utcnow()
    d = pd.DataFrame({
        'i': [2, 1],
        'f': [1., float('nan')],
        's': ['a', None],
        'd': [now, pd.NaT],
        'b': [True, False]
    })
    assert 'bool' in str(d.b.dtype)
    assert 'int' in str(d.i.dtype)
    assert 'datetime' in str(d.d.dtype)
    assert 'object' in str(d.s.dtype)
    assert 'float' in str(d.f.dtype)

    prev_expr = ''
    for col in d.columns:
        new_d = query(d, f'{col}.notna()')
        assert len(new_d) == 2 if col in ('i', 'b') else 1
        # test with categorical data:
        new_col = col + '_cat'
        d[new_col] = d[col].astype('category')
        new_d = query(d, f'{new_col}.notna()')
        assert len(new_d) == 2 if col in ('i', 'b') else 1
        new_d = query(d, f'{new_col}.notna')
        assert len(new_d) == 2 if col in ('i', 'b') else 1
        # just test some series method works (no assert):
        if col in ('b', 'i', 'f', 'd'):
            for method in ('median', 'mean', 'max', 'min'):
                query(d, f'{col} == {col}.{method}')
                query(d, f'{col} == {col}.{method}()')
        else:
            with pytest.raises(TypeError) as terr:  # unsupported for string:
                for method in ('median', 'mean', 'max', 'min'):
                    query(d, f'{col} == {col}.{method}')
                    query(d, f'{col} == {col}.{method}()')
        with pytest.raises(TypeError) as terr:  # unsupported for categorical:
            query(d, f'{new_col} == {new_col}.{method}')
            query(d, f'{new_col} == {new_col}.{method}()')
        # test querying first column:
        query_expr = f'{col} == {d[col].values.tolist()[0]}'
        if col == 'b':
            query_expr = query_expr.replace('True', 'true')
        elif col == 's':
            query_expr = f'{col} == "{d[col].values.tolist()[0]}"'
        elif col == 'd':
            query_expr = f'{col} < datetime({now.year +1}, {now.month}, {now.day})'
        # test equality with first line
        new_d = query(d, query_expr)
        assert len(new_d) == 1
        # if col not in ('b', 'i'):
        #     pd.testing.assert_frame_equal(new_d, query(d, query_expr.replace('==', '>=')))
        #     pd.testing.assert_frame_equal(new_d, query(d, query_expr.replace('==', '<=')))
        #     assert len(query(d, query_expr.replace('==', '>'))) == \
        #         len(query(d, query_expr.replace('==', '<'))) == 0
        # test lower than 1st line
        if not prev_expr:
            prev_expr = query_expr
        else:
            prev_expr += f' & ({query_expr})'
            new_d2 = query(d, prev_expr)
            pd.testing.assert_frame_equal(new_d, new_d2)
