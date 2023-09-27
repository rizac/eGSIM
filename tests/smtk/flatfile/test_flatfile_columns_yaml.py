"""
Created on 16 Feb 2018

@author: riccardo
"""
from datetime import datetime

from typing import Any, Union

import yaml
import pandas as pd
import numpy as np

from egsim.smtk import get_gsim_names, get_rupture_params_required_by, \
    get_sites_params_required_by, get_distances_required_by
from egsim.smtk.flatfile.columns import (ColumnType, ColumnDtype,
                                         _extract_from_columns,
                                         _ff_metadata_path, cast_value)


def test_flatfile_extract_from_yaml():
    """Test the flatfile metadata"""

    with open(_ff_metadata_path) as _:
        dic = yaml.safe_load(_)
        all_names = set(dic)
        all_aliases = set()
        for k, v in dic.items():
            aliases = v.get('alias', None)
            if aliases is None:
                continue
            if isinstance(aliases, str):
                aliases = [aliases]
            assert isinstance(aliases, list)
            assert all(isinstance(_, str) for _ in aliases)
            len_aliases = len(aliases)
            aliases = set(aliases)
            assert len(aliases) == len_aliases, f"Duplicated alias defined for {k}"
            dupes = aliases & all_aliases
            if dupes:
                raise ValueError(f"alias(es) {dupes} already defined as alias")
            all_aliases.update(aliases)
            dupes = aliases & all_names
            if dupes:
                raise ValueError(f"alias(es) {dupes} already defined as name")

    c_type, c_alias = {}, {}
    c_rupture, c_sites, c_dist, c_imts = set(), set(), set(), set()
    c_dtype, c_default, c_help, c_bounds = {}, {}, {}, {}
    _extract_from_columns(dic, rupture_params=c_rupture,
                         sites_params=c_sites,
                         distances=c_dist, imts=c_imts,
                         dtype=c_dtype, default=c_default, help=c_help,
                         alias=c_alias, bounds=c_bounds)

    # Check column properties within itself (no info on other columns required):
    for c in dic:
        c_type = None
        if c in c_rupture:
            c_type = ColumnType.rupture
        elif c in c_sites:
            c_type = ColumnType.sites
        elif c in c_dist:
            c_type = ColumnType.distance
        elif c in c_imts:
            c_type = ColumnType.intensity
        props = {'ctype': c_type, 'name': c}
        if c in c_dtype:
            props['dtype'] = c_dtype.pop(c)
        if c in c_default:
            props['default'] = c_default.pop(c)
        if c in c_help:
            props['chelp'] = c_help.pop(c)
        props['alias'] = c_alias[c]
        if c in c_bounds:
            props['bounds'] = c_bounds.pop(c)
        check_column_metadata(**props)

    # Check that the columns we defined as rupture param, sites param,  distance
    # and intensity measure are implemented in OpenQuake (e.g. no typos).
    # Before that however, note that we cannot use
    # c_rupture, c_sites and c_distances because they are set containing all names
    # and aliases mixed up. As such, separate names and aliases in the following
    # dicts (column name as dict key, column aliases as dict values):
    rup, site, dist = {}, {}, {}
    for n in dic:
        if n in c_rupture:
            rup[n] = c_alias[n]
        elif n in c_sites:
            site[n] = c_alias[n]
        elif n in c_dist:
            dist[n] = c_alias[n]
    # now check names with openquake names:
    check_with_openquake(rup, site, dist, c_imts)


class missingarg:
    pass


def check_column_metadata(*, name: str, ctype: Union[ColumnType, None],
                          alias:set[str, ...],
                          dtype:Union[ColumnDtype, pd.CategoricalDtype]=None,
                          default:Any=missingarg,
                          bounds:dict[str, Any]=missingarg,
                          chelp:str = missingarg
                          ):
    """checks the Column metadata dict issued from the YAML flatfile"""
    # nb: use keyword arguments instead of a dict
    # so that we can easily track typos
    prefix = f'Column "{name}" metadata error (check YAML): '
    # convert type to corresponding Enum:
    assert name in alias
    alias_is_missing = alias == {name}

    if ctype == ColumnType.intensity.name and not alias_is_missing:
        raise ValueError(f"{prefix} Intensity measure cannot have alias(es)")

    if chelp is not missingarg and (not isinstance(chelp, str) or not chelp):
        raise ValueError(f"{prefix} set 'help' to a non empty string, or "
                         f"remove the key entirely")

    # perform some check on the data type consistencies:
    bounds_are_given = bounds is not missingarg
    default_is_given = default is not missingarg

    # check dtype null and return in case:
    if dtype is None:
        if bounds_are_given or default_is_given:
            raise ValueError(f"{prefix}  with `dtype` null or missing, "
                             f"you cannot supply `default` and `bounds`")
        return

    # handle categorical data:
    if isinstance(dtype, pd.CategoricalDtype):  # categorical data type
        if ColumnDtype.of_all(dtype.categories) is None:
            raise ValueError(f"{prefix} invalid data type(s) in categorical data")
        if bounds_are_given:
            raise ValueError(f"{prefix} bounds cannot be provided with "
                             f"categorical data type")
        if default_is_given:
            assert default is cast_value(default, dtype)  # raise if not in categories
        return

    assert isinstance(dtype, ColumnDtype)

    if dtype in (ColumnDtype.int, ColumnDtype.bool) and not default_is_given:
        raise ValueError('int or bool with no default')


    # check bounds:
    if bounds_are_given:
        symbols = {"<", ">", ">=", "<="}
        assert all(k in symbols for k in bounds), \
            f"Some bound symbols not in {str(symbols)}, check flatfile Python" \
            f"and flatfile metadata YAML file"
        if len(bounds) > 2:
            raise ValueError(f'{prefix} too many bounds: {list(bounds)}')
        if (">" in bounds and ">=" in bounds) or \
                ("<" in bounds and "<=" in bounds):
            raise ValueError(f'{prefix} invalid bounds combination: {list(bounds)}')
        max_val = bounds.get("<", bounds.get("<=", None))
        min_val = bounds.get(">", bounds.get(">=", None))
        for val in [max_val, min_val]:
            if val is not None:
                assert val is cast_value(val, dtype)
        if max_val is not None and min_val is not None and max_val <= min_val:
            raise ValueError(f'{prefix} min. bound must be lower than '
                             f'max. bound')

    # check default value:
    if default_is_given:
        assert default is cast_value(default, dtype)


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

    for name in get_gsim_names():
        oq_rupture_params.update(get_rupture_params_required_by(name))
        oq_sites_params.update(get_sites_params_required_by(name))
        oq_distances.update(get_distances_required_by(name))

    for name in rupture_params:
        if name not in oq_rupture_params:
            assert len(set(rupture_params[name]) & oq_rupture_params) == 1

    for name in sites_params:
        if name not in oq_sites_params:
            assert len(set(sites_params[name]) & oq_sites_params) == 1

    for name in distances:
        if name not in distances:
            assert len(set(distances[name]) & oq_distances) == 1

    from openquake.hazardlib import imt

    for ix in imts:
        x = getattr(imt, ix)
        assert callable(x)


def test_Column_dtype():
    vals = {
        datetime.utcnow(): ColumnDtype.datetime,
        2: ColumnDtype.int,
        1.2: ColumnDtype.float,
        True: ColumnDtype.bool,
        'a': ColumnDtype.str
    }
    for val, ctype in vals.items():
        assert ColumnDtype.of(val) == ctype
        assert ColumnDtype.of(type(val)) == ctype
        assert ColumnDtype.of_all(pd.CategoricalDtype([val]).categories) == ctype

    d = pd.DataFrame({
        'int': [4, 5],
        'float': [1.1, np.nan],
        'datetime': [datetime.utcnow(), datetime.utcnow()],
        'bool': [True, False],
        'str': [None, "x"]
    })
    d.str = d.str.astype('string')
    for c in d.columns:
        dtyp = d[c].dtype
        assert ColumnDtype.of(dtyp) == ColumnDtype[c]
        assert ColumnDtype.of(d[c]) == ColumnDtype[c]
        assert ColumnDtype.of(d[c].values) == ColumnDtype[c]
        assert all(ColumnDtype.of(_) == ColumnDtype[c] for _ in d[c] if pd.notna(_))
        assert all(ColumnDtype.of(_) == ColumnDtype[c] for _ in d[c].values if pd.notna(_))

    assert ColumnDtype.of(None) is None
