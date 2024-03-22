"""
Created on 16 Feb 2018

@author: riccardo
"""
import tempfile

from io import StringIO
import os
from datetime import datetime

import numpy as np
import pytest
import pandas as pd
from pandas import StringDtype

from egsim.smtk.flatfile import read_flatfile, query, ColumnType, InvalidDataInColumn, \
    get_dtype_of, ColumnDtype
from egsim.smtk.flatfile import ColumnsRegistry, _load_columns_registry


def test_read_flatifle_yaml():

    dic = _load_columns_registry(False)
    params = ColumnsRegistry.get_rupture_params()
    assert len({'rupture_width', 'mag', 'magnitude', 'width'} & params) == 4
    params = {c for c in dic if ColumnsRegistry.get_type(c) == ColumnType.distance}
    assert len({'rrup', 'rhypo'} & params) == 2
    params = {c for c in dic if ColumnsRegistry.get_type(c) == ColumnType.site}
    assert len({'sta_lat', 'station_latitude', 'lat' , 'vs30'} & params) == 4


def test_flatfile_turkey():
    # FIXME handle paths, fixtures wrt django tests. HArdcoding path for the moment:
    root = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    fpath = os.path.join(root, 'data', 'tk_20230206_flatfile_geometric_mean.csv')
    dfr = read_flatfile(fpath)
    assert all(get_dtype_of(dfr[c]) is not None for c in dfr.columns)
    fpath = fpath+'.hdf.tmp'
    try:
        dfr.to_hdf(fpath, format='table', key='egsim')
        dfr2 = read_flatfile(fpath)
        pd.testing.assert_frame_equal(dfr, dfr2)
    finally:
        os.remove(fpath)

# def test_read_flatfile_dtypes(datdir):
#     f = '/Users/rizac/work/gfz/projects/sources/python/egsim/tests/data/tmp'
#
#     data = [True, False]
#     exp_dtype = ColumnDtype.bool
#
#     assert get_dtype_of(data) == exp_dtype
#     d = pd.DataFrame({'PGA': [1.]* len(data), 'test':data})
#     assert d['test'] == exp_dtype
#     assert d['PGA'] == ColumnDtype.float
#
#     with open(f, 'w') as _:
#         d.to_hdf(f)
#     d = read_flatfile(f)
#     assert d['test'] == exp_dtype
#     assert d['PGA'] == ColumnDtype.float
#     d = read_flatfile(f, dtypes={'test': ColumnDtype.category})
#     assert d['test'] == exp_dtype
#     assert d['PGA'] == ColumnDtype.category
#
#     with open(f, 'w') as _:
#         d.to_csv(f)
#     d = read_flatfile(f)
#     assert d['test'] == exp_dtype
#     assert d['PGA'] == ColumnDtype.float




def tst_read_csv():
    # we rely on the fact that dataframe get returns none when column not found:
    assert pd.DataFrame().get('a') is None
    assert pd.DataFrame({'a': [1,2]}).get('b') is None

    args = {
        'dtype': {"str": "str", "PGA": "float",
                  "int": "int", "datetime": "datetime", "bool": "bool"},
    }

    expected = {
        'int': np.dtype('int64'),
        'PGA': np.dtype('float64'),
        'bool': np.dtype('bool'),
        'datetime': np.dtype('<M8[ns]'),
        'str': StringDtype(),  # np.dtype('O'),
        'category': np.dtype('O')
    }

    # print("\nData ok")
    csv = ("int,bool,PGA,datetime,str,category"
           "\n"
           "1,true,1.1,2006-01-01T00:00:00,x,a"
           "\n"
           "1,true,1.1,2006-01-01T00:00:00,x,ax")
    d = read_flatfile(StringIO(csv), **args)  # noqa
    assert d.dtypes.to_dict() == expected
    for c in d.columns:
        assert not pd.isna(d[c]).any()

    # print("\nData ok and empty")
    expected_na_count = {
        'int': 0, 'bool': 0, 'PGA':1, 'datetime': 1, 'str': 1, 'category': 1
    }
    csv = ("int,bool,PGA,datetime,str,category"
           "\n"
           ",,,,,"
           "\n"
           "1,true,1.1,2006-01-01T00:00:00,x,ax")
    d = read_flatfile(StringIO(csv), **args, defaults={'int':0, 'bool':False})  # noqa
    assert d.dtypes.to_dict() == expected
    for c in d.columns:
        assert pd.isna(d[c]).sum() == expected_na_count[c]

    # print("\nSome data ok, empty and wrong")
    csv = ("int,bool,PGA,datetime,str,category"
           "\n"
           "1,true,1.1,2006-01-01T00:00:00,x,a"
           )
    # loop throguh all CSV columns defined above (int, then bool, and so on):
    for header, val in zip(csv.split("\n")[0].split(","), csv.split("\n")[1].split(",")):
        # append an x to the last value
        csv2 = f"{header}\n{val}\n{val}x"
        if header in ('int', 'bool', 'PGA', 'datetime'):
        # try:
        #     d = read_flatfile(StringIO(csv2), **args)
        #     asd = 9
        # except Exception as exc:
        #     pass
        # continue
            with pytest.raises(InvalidDataInColumn) as verr:
                d = read_flatfile(StringIO(csv2), **args)  # noqa
                # check that the column is in the exception message:
            assert header in str(verr.value)
            continue
        d = read_flatfile(StringIO(csv2), **args)


def tst_read_csv_bool():
    args = {
        'sep': ';',
        'skip_blank_lines': False,
        # the above arg is needed (default is True) because
        # we have a single column
        # and missing values are input as blank lines
        'dtype': {"str": "str", "float": "float",
                  "int": "int", "datetime": "datetime", "bool": "bool"},
    }
    expected = [True, True, True, False, False, False]
    csv_str = "bool\n1\nTrue\ntrue\n0\nFalse\nfalse"
    d = read_flatfile(StringIO(csv_str), **args)  # noqa
    assert (d['bool'] == expected).all()

    # Insert a missing value at the beginning (defaults to False).
    # NOTE: appending a missing value (empty line) is skipped even if skip_blank_lines is
    # True (as it is probably interpreted as ending newline of the previous csv row?)
    csv_str = csv_str.replace("bool\n", "bool\n\n")
    d = read_flatfile(StringIO(csv_str), **args, defaults={'bool': False})  # noqa
    assert (d['bool'] == [False] + expected).all()

    # Append invalid value (float not in [0, 1]):
    with pytest.raises(ValueError):
        d = read_flatfile(StringIO("bool\n1\nTrue\ntrue\nFalse\nfalse\n1.1"), **args)  # noqa

    # Append invalid value ("X"):
    with pytest.raises(ValueError):
        d = read_flatfile(StringIO("bool\n1\nTrue\ntrue\nFalse\nfalse\nX"), **args)  # noqa

    # int series is ok
    csv_str = "bool\n1\n1\n1\n0\n0\n0"
    d = read_flatfile(StringIO(csv_str), **args)  # noqa
    assert (d['bool'] == expected).all()
    with pytest.raises(ValueError):
        # int series must have only 0 and 1:
        csv_str += "\n2"
        d = read_flatfile(StringIO(csv_str), **args)  # noqa

    # float series is ok
    csv_str = "bool\n1.0\n1.0\n1.0\n0.0\n0.0\n0.0"
    d = read_flatfile(StringIO(csv_str), **args)  # noqa
    assert (d['bool'] == expected).all()
    with pytest.raises(ValueError):
        # float series must have only 0 and 1:
        csv_str += "\n0.1"
        d = read_flatfile(StringIO(csv_str), **args)  # noqa


def tst_read_csv_categorical():
    defaults = {
        "str": "a",
        "int": 1,
        "float": 1.1,
        "datetime": datetime.fromisoformat('2006-01-01T00:00:00'),
        "bool": True,
    }
    dtypes = { x: pd.CategoricalDtype([defaults[x]]) for x in defaults }

    # print("\nData ok")
    csv = ("int,bool,float,datetime,str"
           "\n"
           "1,true,1.1,2006-01-01T00:00:00,a"
           "\n"
           "1,true,1.1,2006-01-01T00:00:00,a")
    d = read_flatfile(StringIO(csv), dtype=dict(dtypes))  # noqa
    for c in d.columns:
        assert d[c].dtype == dtypes[c]
        assert sorted(d[c].dtype.categories.tolist()) == \
               sorted(dtypes[c].categories.tolist())
        assert not pd.isna(d[c]).any()

    # print("\nData ok")
    csv = ("int,bool,float,datetime,str"
           "\n"
           "1,true,1.1,2006-01-01T00:00:00,a"
           "\n"
           ",,,,")
    d = read_flatfile(StringIO(csv), dtype=dict(dtypes))  # noqa
    for c in d.columns:
        assert d[c].dtype == dtypes[c]
        assert sorted(d[c].dtype.categories.tolist()) == \
               sorted(dtypes[c].categories.tolist())
        assert pd.isna(d[c]).sum() == 1

    # print("\nSome missing data, some data wrong")
    for header, val in zip(csv.split("\n")[0].split(","), csv.split("\n")[1].split(",")):
        csv2 = f"{header}\n{val}\n{val}x"
        with pytest.raises(ValueError) as verr:
            d = read_flatfile(StringIO(csv2), dtype=dict(dtypes))  # noqa
            # check that the column is in the exception message:
        assert header in str(verr.value)


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
            query_expr = f'{col} <= datetime("{now.isoformat()}")'
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
