"""
Created on 16 Feb 2018

@author: riccardo
"""

import os
from datetime import datetime

import pytest
import pandas as pd

from egsim.smtk import flatfile
from egsim.smtk.flatfile import (read_flatfile,
                                 query,
                                 ColumnType,
                                 FlatfileError,
                                 get_dtype_of)
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


def test_flatfile_exceptions():
    for exc in dir(flatfile):
        exc_cls = getattr(flatfile, exc, None)
        try:
            is_subcls = issubclass(exc_cls, FlatfileError)
        except TypeError:
            continue
        if not is_subcls:
            continue

        for cols in [['hypo_lat'], ['unknown'], ['hypo_lat', 'st_lon'],
                     ['hypo_lat', 'unknown'],
                     ['st_lon', 'hypo_lat', 'unknown']]:

            exc = exc_cls(*cols)
            assert all(_ in str(exc) for _ in cols)

            try:
                raise exc_cls(*cols)
            except FlatfileError as exc:
                import traceback
                from io import StringIO
                s = StringIO()
                traceback.print_exc(file=s)
                strr = s.getvalue()
                assert f'{exc_cls.__name__}:' in strr
                assert ", ".join(str(_) for _ in cols) in strr
