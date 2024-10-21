"""
Created on 16 Feb 2018

@author: riccardo
"""
from itertools import combinations

import pytest
from datetime import datetime

import yaml
import pandas as pd
import numpy as np

from openquake.hazardlib import imt
from egsim.smtk import gsim, registered_imts, registered_gsims
from egsim.smtk.flatfile import (ColumnType, ColumnDtype,
                                 _flatfile_metadata_path, cast_to_dtype,
                                 FlatfileMetadata,
                                 _load_flatfile_metadata, get_dtype_of,
                                 validate_flatfile_dataframe,
                                 ColumnDataError)


def test_flatfile_extract_from_yaml():
    """Test the flatfile metadata"""

    # read directly from columns registry and asure aliases are well formed.
    # Do not use _load_column_registry because it is assumed to rely on the following
    # test passing (no duplicates, no single alias euqal to column name, and so on):
    with open(_flatfile_metadata_path) as _:
        dic = yaml.safe_load(_)
        all_names = set(dic)
        all_aliases = set()
        for k, v in dic.items():
            if 'aliases' not in v:
                continue
            aliases = v['aliases']
            if isinstance(aliases, str):
                aliases = [aliases]
            assert isinstance(aliases, list)
            len_aliases = len(aliases)
            assert len_aliases > 0
            assert k not in aliases
            assert all(isinstance(_, str) for _ in aliases)
            aliases = set(aliases)
            assert len(aliases) == len_aliases, f"Duplicated alias defined for {k}"
            dupes = aliases & all_aliases
            if dupes:
                raise ValueError(f"alias(es) {dupes} already defined as alias")
            all_aliases.update(aliases)
            dupes = aliases & all_names
            if dupes:
                raise ValueError(f"alias(es) {dupes} already defined as name")

    # Check column properties within itself (no info on other columns required):
    for c, props in _load_flatfile_metadata(False).items():
        check_column_metadata(name=c, props=dict(props))

    # Check that the columns we defined as rupture param, sites param,  distance
    # and intensity measure are implemented in OpenQuake (e.g. no typos).
    # Before that however, note that we cannot use
    # c_rupture, c_sites and c_distances because they are set containing all names
    # and aliases mixed up. As such, separate names and aliases in the following
    # dicts (column name as dict key, column aliases as dict values):
    rup, site, dist, imtz = {}, {}, {}, set()
    for n in dic:
        c_type = FlatfileMetadata.get_type(n)
        aliases = FlatfileMetadata.get_aliases(n)
        if c_type == ColumnType.rupture:
            rup[n] = set(aliases)
        elif c_type == ColumnType.site:
            site[n] = set(aliases)
        elif c_type == ColumnType.distance:
            dist[n] = set(aliases)
        elif c_type == ColumnType.intensity:
            imtz.add(n)

    # now check names with openquake names:
    check_with_openquake(rup, site, dist, imtz)


def check_column_metadata(*, name: str, props: dict):
    """checks the Column metadata dict issued from the YAML flatfile"""
    # nb: use keyword arguments instead of a dict
    # so that we can easily track typos
    prefix = f'Column "{name}" metadata error (check YAML): '
    # convert type to corresponding Enum:
    alias = props.pop('alias')
    assert name in alias
    alias_is_missing = set(alias) == {name}

    type = props.pop('type', None)
    if type == ColumnType.intensity.name and not alias_is_missing:
        raise ValueError(f"{prefix} Intensity measure cannot have alias(es)")

    if 'help' in props:
        help = props.pop('help')
        if not isinstance(help, str) or not help:
            raise ValueError(f"{prefix} set 'help' to a non empty string, or "
                             f"remove the key entirely")

    # perform some check on the data type consistencies:
    bounds_symbols = {"<", ">", ">=", "<="}
    bounds_are_given = any(k in props for k in bounds_symbols)
    bounds = None
    if bounds_are_given:
        bounds = {k: props.pop(k) for k in bounds_symbols if k in props}
    default_is_given = 'default' in props
    default = None
    if default_is_given:
        default = props.pop('default')

    # check dtype null and return in case:
    dtype = props.pop('dtype', None)
    if dtype is None:
        if bounds_are_given or default_is_given:
            raise ValueError(f"{prefix}  with `dtype` null or missing, "
                             f"you cannot supply `default` and `bounds`")
        return

    # handle categorical data:
    if isinstance(dtype, pd.CategoricalDtype):  # categorical data type
        if get_dtype_of(dtype.categories) is None:  # noqa
            raise ValueError(f"{prefix} invalid data type(s) in categorical data")
        if bounds_are_given:
            raise ValueError(f"{prefix} bounds cannot be provided with "
                             f"categorical data type")
        if default_is_given:
            assert default is cast_to_dtype(default, dtype)  # noqa
        return

    dtype = ColumnDtype(dtype)

    if dtype in (ColumnDtype.int, ColumnDtype.bool) and not default_is_given:
        raise ValueError(f'{prefix} int or bool with no default')

    # check bounds:
    if bounds_are_given:
        if len(bounds) > 2:
            raise ValueError(f'{prefix} too many bounds: {list(bounds)}')
        if (">" in bounds and ">=" in bounds) or \
                ("<" in bounds and "<=" in bounds):
            raise ValueError(f'{prefix} invalid bounds combination: {list(bounds)}')
        max_val = bounds.get("<", bounds.get("<=", None))
        min_val = bounds.get(">", bounds.get(">=", None))
        for val in [max_val, min_val]:
            if val is not None:
                assert val == cast_to_dtype(val, dtype)
        if max_val is not None and min_val is not None and max_val <= min_val:
            raise ValueError(f'{prefix} min. bound must be lower than '
                             f'max. bound')

    # check default value:
    if default_is_given:
        assert default == cast_to_dtype(default, dtype)

    if props:
        raise ValueError(f'{prefix} Undefined property names, '
                         f'remove from YAML: {list(props.keys())}')


def check_with_openquake(rupture_params: dict[str, set[str]],
                         sites_params: dict[str, set[str]],
                         distances: dict[str, set[str]],
                         imts: set[str]):
    """Checks that the flatfile columns with a specific Type set
    (columns.ColumnType) match the OpenQuake corresponding name
    """
    oq_rupture_params = set()
    oq_sites_params = set()
    oq_distances = set()

    for name in registered_gsims:
        try:
            model = gsim(name)
        except (TypeError, ValueError, FileNotFoundError, OSError, AttributeError,
                IndexError, KeyError, DeprecationWarning) as _:
            continue
        oq_rupture_params.update(model.REQUIRES_RUPTURE_PARAMETERS)
        oq_sites_params.update(model.REQUIRES_SITES_PARAMETERS)
        oq_distances.update(model.REQUIRES_DISTANCES)

    for name in rupture_params:
        if name in {'evt_id', 'evt_time'}:
            continue  # defined in yaml, not in openquake
        if name not in oq_rupture_params:
            assert len(set(rupture_params[name]) & oq_rupture_params) == 1

    for name in sites_params:
        if name in {'sta_id', 'event_id'}:
            continue  # defined in yaml, not in openquake
        if name not in oq_sites_params:
            assert len(set(sites_params[name]) & oq_sites_params) == 1

    for name in distances:
        if name not in oq_distances:
            assert len(set(distances[name]) & oq_distances) == 1

    for ix in imts:
        x = getattr(imt, ix)
        assert callable(x) and x.__name__ in registered_imts


def test_get_dtype():
    vals = [
        [ColumnDtype.datetime, datetime.utcnow()],
        [ColumnDtype.datetime, np.datetime64(datetime.utcnow())],
        [ColumnDtype.int, 2],
        [ColumnDtype.int, np.int_(2)],
        [ColumnDtype.float, 2.2],
        [ColumnDtype.float, np.nan],
        [ColumnDtype.float, np.float_(2.2)],
        [ColumnDtype.bool, True],
        [ColumnDtype.bool, np.bool_(False)],
        [ColumnDtype.str, 'a'],
        [ColumnDtype.str, np.str_('a')],
    ]
    for ctype, val in vals:
        # scalar (Pythion numpy whatever):
        assert get_dtype_of(val) == ctype
        # pd.Series:
        assert get_dtype_of(pd.Series(val)) == ctype
        assert get_dtype_of(pd.Series([val])) == ctype
        # pd.CategoricalDtype
        if not pd.isna(val):
            # (NaN / Null cannot be set as categories, skip in case)
            assert get_dtype_of(pd.CategoricalDtype([val]).categories) == ctype
        # pd.Index:
        assert get_dtype_of(pd.Index([val])) == ctype
        # np.dtypes:
        assert get_dtype_of(pd.Series(val).dtype) == ctype
        assert get_dtype_of(pd.Series([val]).dtype) == ctype
        # np.array:
        assert get_dtype_of(pd.Series(val).values[0]) == ctype
        assert get_dtype_of(pd.Series([val]).values) == ctype
        # pd.numeric and pd.to_datetime
        if ctype in (ColumnDtype.float, ColumnDtype.bool, ColumnDtype.int):
            assert get_dtype_of(pd.to_numeric(val)) == ctype
            assert get_dtype_of(pd.to_numeric([val])) == ctype
        elif ctype == ColumnDtype.datetime:
            # to_datetime returns a Timestamp, so it is not datetime dtype:
            assert get_dtype_of(pd.to_datetime(val)) == ctype
            assert get_dtype_of(pd.to_datetime([val])) == ctype
        # NOTE: NUMPY IS ACTUALLY NOT SUPPORTED, THE CODE BELOW IS LEGACY CODE:
        # IF IT FAILS AND THE FIX IS A PAIN, YOU CAN REMOVE THE TEST
        if ctype != ColumnDtype.datetime:
            # skip np.array(datetime) and use to_datetime (see above):
            assert get_dtype_of(np.array(val)) == ctype
            assert get_dtype_of(np.array([val])) == ctype

    # cases of mixed types that return None as dtype (by default they return string
    # but this is a behaviour of pandas that we do not want to mimic):
    assert get_dtype_of(pd.Series([True, 2])) is None
    assert get_dtype_of(pd.CategoricalDtype([True, 2]).categories) is None

    assert get_dtype_of(pd.Series(['True', 2])) is None
    assert get_dtype_of(pd.CategoricalDtype(['True', 2]).categories) is None

    assert get_dtype_of(pd.Series(['x', 2, datetime.utcnow()])) is None
    assert get_dtype_of(pd.CategoricalDtype(['x', 2, datetime.utcnow()]).categories) \
           is None

    # test series with N/A (more complete tests in the next function):
    vals = [
        [[datetime.utcnow(), pd.NaT], ColumnDtype.datetime],
        [[2, None], ColumnDtype.float],
        [[1.2, None], ColumnDtype.float],
        [[True, None], None],
        [['a', None], ColumnDtype.str]
    ]
    for val, ctype in vals:
        assert get_dtype_of(pd.Series(val)) == ctype


def test_flatfile_invalid_categories():
    d = pd.DataFrame({'geology': ['UNKNOWN'], 'PGA': [1.2]})
    validate_flatfile_dataframe(d)

    d = pd.DataFrame({'geology': ['?'], 'PGA': [1.2]})
    with pytest.raises(ColumnDataError) as err:
        validate_flatfile_dataframe(d)


def test_get_dtype_mixed_categories():
    """test that get_dtypoe_of mixed categorical returns None and not
    ColumnDtype.category"""
    assert get_dtype_of(pd.Series([2, True]).astype('category')) is None
    assert (get_dtype_of(pd.Series([False, True]).astype('category'))
            is ColumnDtype.category)
    assert (get_dtype_of(pd.Series([False, None]).astype('category'))
            is ColumnDtype.category)
    assert get_dtype_of(pd.Series([datetime.utcnow(), pd.NaT]).astype(
        'category')) is ColumnDtype.category
    assert get_dtype_of(pd.Series([2, 3]).astype(
        'category')) is ColumnDtype.category
    assert get_dtype_of(pd.Series([2, None]).astype(
        'category')) is ColumnDtype.category
    assert get_dtype_of(pd.Series([2, np.nan]).astype(
        'category')) is ColumnDtype.category
    assert get_dtype_of(pd.Series([2, 2.2]).astype(
        'category')) is ColumnDtype.category
    assert get_dtype_of(pd.Series(['2', 'None']).astype(
        'category')) is ColumnDtype.category
    assert get_dtype_of(pd.Series(['2', None]).astype(
        'category')) is ColumnDtype.category


def test_mixed_arrays_are_mostly_null_dtype():
    """test that arrays with mixed dtypes have None dtype (with some known exceptions)"""
    for val in combinations(['a', 2, 2.2, True, datetime.utcnow()], 2):
        # check that the two values have a dtype set:
        assert get_dtype_of(val[0]) is not None
        assert get_dtype_of(val[1]) is not None

        val = list(val)

        # test pandas Series:
        cdtype = None
        try:
            cdtype = get_dtype_of(pd.Series(val))
            assert cdtype is None
        except AssertionError:
            if set(val) == {2, 2.2} and cdtype == ColumnDtype.float:
                pass

        # test numpy arrays
        # NOTE: NUMPY IS ACTUALLY NOT SUPPORTED, THE CODE BELOW IS LEGACY CODE:
        # IF IT FAILS AND THE FIX IS A PAIN, YOU CAN REMOVE THE TEST
        cdtype = None
        try:
            cdtype = get_dtype_of(np.array(val))
            assert cdtype is None
        except AssertionError:
            # numpy behaves differently than pandas:
            # everything with 'a' is converted to str:
            if 'a' in val:
                assert cdtype == ColumnDtype.str
                continue
            # if we have 2 and True, then the dtype is converted to int:
            if set(val) == {2, True}:
                assert cdtype == ColumnDtype.int
                continue
            # for any combination of 2.2 with 2 or True, dtype is converted to float:
            if all(_ in {2.2, 2, True} for _ in val):
                assert cdtype == ColumnDtype.float


def test_dtypes_with_null():
    """test that arrays with known dtype + 1 null preserve their dtype"""
    for val in ['a', 2, 2.2, True, datetime.utcnow()]:
        # check that the two values have a dtype set:
        cdtype = get_dtype_of(val)
        assert cdtype is not None

        vals = [val, None]
        # test pandas Series:
        try:
            assert cdtype == get_dtype_of(pd.Series(vals))
        except AssertionError:
            assert cdtype in (ColumnDtype.int, ColumnDtype.bool)

        # test numpy array:
        # NOTE: NUMPY IS ACTUALLY NOT SUPPORTED, THE CODE BELOW IS LEGACY CODE:
        # IF IT FAILS AND THE FIX IS A PAIN, YOU CAN REMOVE THE TEST
        try:
            assert cdtype != get_dtype_of(np.array(vals))
        except AssertionError:
            assert cdtype == ColumnDtype.str


def test_str_and_o_dtypes_are_the_same():
    """test that a Series of strings and a Series of strings and Nones have the
    same dtype"""
    s1 = pd.Series(['s'])
    s2 = pd.Series(['s', None])
    assert s1.dtype == np.dtype('O')
    assert s2.dtype == np.dtype('O')
    assert pd.api.types.is_string_dtype(s1) != pd.api.types.is_string_dtype(s2)


def test_cast_to_dtype():
    vals = [
        [ColumnDtype.datetime, datetime.utcnow()],
        [ColumnDtype.datetime, np.datetime64(datetime.utcnow())],
        [ColumnDtype.int, 2],
        [ColumnDtype.int, np.int_(2)],
        [ColumnDtype.float, 2.2],
        [ColumnDtype.float, np.nan],
        [ColumnDtype.float, np.float_(2.2)],
        [ColumnDtype.bool, True],
        [ColumnDtype.bool, np.bool_(False)],
        [ColumnDtype.str, 'a'],
        [ColumnDtype.str, np.str_('a')],
    ]

    def eq(a, b):
        try:
            return np.array_equal(a, b, equal_nan=True)
        except TypeError:
            if pd.api.types.is_list_like(a) and pd.api.types.is_list_like(b):
                return len(a) == len(b) and all(_1 == _2 for _1, _2 in zip(a,b))
            elif pd.api.types.is_scalar(a) and pd.api.types.is_scalar(b):
                return a == b
            elif isinstance(a, np.ndarray) and isinstance(b, np.ndarray) and \
                    not a.shape and not b.shape:
                return a.item() == b.item()

    for ctype, val in vals:
        for as_categories in [True, False]:
            if as_categories:
                try:
                    ctype = pd.CategoricalDtype([val])
                except ValueError:
                    if val != val:
                        continue
                    raise

            # scalar (Python numpy whatever):
            assert eq(cast_to_dtype(val, ctype), val)

            # pd.Series:
            v = pd.Series(val)
            assert eq(cast_to_dtype(v, ctype), v)
            v = pd.Series(val)
            assert eq(cast_to_dtype(v, ctype) , v)
            # pd.Index:
            v = pd.Index([val])
            assert eq(cast_to_dtype(v, ctype), v)

            # pd.numeric and pd.to_datetime
            if ctype in (ColumnDtype.float, ColumnDtype.bool, ColumnDtype.int):
                assert eq(cast_to_dtype(pd.to_numeric(val), ctype), val)
                assert eq(cast_to_dtype(pd.to_numeric([val]), ctype), [val])  # noqa
            elif ctype == ColumnDtype.datetime:
                # to_datetime returns a Timestamp so it is not datetime dtype:
                assert eq(cast_to_dtype(pd.to_datetime(val), ctype), val)
                assert eq(cast_to_dtype(pd.to_datetime([val]), ctype), [val])  # noqa

    # mixed types categories in categorical data raises:
    with pytest.raises(ValueError) as verr:
        cast_to_dtype('r', pd.CategoricalDtype([1, 'd']))

    # mixed types values in series with dtype.category raises:
    with pytest.raises(ValueError) as verr:
        cast_to_dtype(pd.Series([2, True]), ColumnDtype.category)

    # mixed types values in series with dtype.category and 'coerce' works:
    v = cast_to_dtype(pd.Series([2, True]), ColumnDtype.category,
                      mixed_dtype_categorical='coerce')
    assert v.tolist() == ['2', 'True']

    # mixed types values in series with dtype.str works:
    v = cast_to_dtype(pd.Series([2, True]), ColumnDtype.str)
    assert v.tolist() == ['2', 'True']

    # mixed types values in series with dtype.float works:
    v = cast_to_dtype(pd.Series([2, True]), ColumnDtype.float)
    assert v.tolist() == [2.0, 1.0]

    # mixed types values in series with dtype.bool raises as 2 isn't recognized:
    with pytest.raises(ValueError) as verr:
        cast_to_dtype(pd.Series([2, True]), ColumnDtype.bool)
    # this should work:
    v = cast_to_dtype(pd.Series([0, True]), ColumnDtype.bool)
    assert v.tolist() == [False, True]
