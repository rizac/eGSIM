"""
Created on 16 Feb 2018

@author: riccardo
"""
from datetime import datetime

import yaml
import pandas as pd
import numpy as np

from openquake.hazardlib import imt
from egsim.smtk import registered_imts

from egsim.smtk import (registered_gsims,
                        rupture_params_required_by,
                        site_params_required_by,
                        distances_required_by)
from egsim.smtk.flatfile import (ColumnType, ColumnDtype,
                                 _columns_registry_path, cast_value, ColumnsRegistry,
                                 _load_columns_registry)


def test_flatfile_extract_from_yaml():
    """Test the flatfile metadata"""

    # read directly from columns registry and asure aliases are well formed.
    # Do not use _load_column_registry because it is assumed to rely on the following
    # test passing (no duplicates, no single alias euqal to column name, and so on):
    with open(_columns_registry_path) as _:
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
    for c, props in _load_columns_registry(False).items():
        check_column_metadata(name=c, props=dict(props))

    # Check that the columns we defined as rupture param, sites param,  distance
    # and intensity measure are implemented in OpenQuake (e.g. no typos).
    # Before that however, note that we cannot use
    # c_rupture, c_sites and c_distances because they are set containing all names
    # and aliases mixed up. As such, separate names and aliases in the following
    # dicts (column name as dict key, column aliases as dict values):
    rup, site, dist, imtz = {}, {}, {}, set()
    for n in dic:
        c_type = ColumnsRegistry.get_type(n)
        aliases = ColumnsRegistry.get_aliases(n)
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
        if ColumnDtype.of(*dtype.categories) is None:
            raise ValueError(f"{prefix} invalid data type(s) in categorical data")
        if bounds_are_given:
            raise ValueError(f"{prefix} bounds cannot be provided with "
                             f"categorical data type")
        if default_is_given:
            assert default is cast_value(default, dtype)  # raise if not in categories
        return

    assert isinstance(dtype, ColumnDtype)

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
                assert val is cast_value(val, dtype)
        if max_val is not None and min_val is not None and max_val <= min_val:
            raise ValueError(f'{prefix} min. bound must be lower than '
                             f'max. bound')

    # check default value:
    if default_is_given:
        assert default is cast_value(default, dtype)

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
        oq_rupture_params.update(rupture_params_required_by(name))
        oq_sites_params.update(site_params_required_by(name))
        oq_distances.update(distances_required_by(name))

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
        assert ColumnDtype.of(*pd.CategoricalDtype([val]).categories) == ctype

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
