"""
Created on 16 Feb 2018

@author: riccardo
"""
from typing import Any, Union

import yaml
import pandas as pd

from egsim.smtk.flatfile import (ColumnType, ColumnDtype, read_column_metadata,
                                 _ff_metadata_path)


def test_flatfile_metadata_from_yaml():
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

    c_name, c_type, c_alias = set(), {}, {}
    c_dtype, c_required, c_default, c_help, c_bounds = {}, [], {}, {}, {}
    read_column_metadata(names=c_name, ctype=c_type, dtype=c_dtype,
                         required=c_required, default=c_default, help=c_help,
                         alias=c_alias, bounds=c_bounds)

    # Check column properties within itself (no info on other columns required):
    for c in c_name:
        props = {'ctype': c_type[c], 'name': c}
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


class missingarg:
    pass


def check_column_metadata(*, name: str, ctype: str, alias:set[str, ...],
                          dtype:Union[str, pd.CategoricalDtype]=missingarg,
                          default:Any=missingarg,
                          bounds:dict[str, Any]=missingarg,
                          chelp:str = missingarg
                          ):
    """checks the Column metadata dict issued from the YAML flatfile"""
    # nb: use keyword arguments instead of a dict
    # so that we can easily track typos
    prefix = f'Column "{name}" metadata error (check YAML): '
    # convert type to corresponding Enum:
    try:
        ctype = ColumnType[ctype]
    except KeyError:
        raise ValueError(f"{prefix} invalid type: {ctype}")

    assert name in alias
    alias_is_missing = alias == {name}

    if ctype == ColumnType.intensity_measure.name and not alias_is_missing:
        raise ValueError(f"{prefix} Intensity measure cannot have alias(es)")

    if chelp is not missingarg and (not isinstance(chelp, str) or not chelp):
        raise ValueError(f"{prefix} set 'help' to a non empty string, or "
                         f"remove the key entirely")

    # perform some check on the data type consistencies:
    bounds_are_given = bounds is not missingarg
    default_is_given = default is not missingarg

    # check dtype null and return in case:
    if dtype is missingarg:
        if bounds_are_given or default_is_given:
            raise ValueError(f"{prefix}  with `dtype` null or missing, "
                             f"you cannot supply `default` and `bounds`")
        return

    # handle categorical data:
    if isinstance(dtype, (list, tuple, pd.CategoricalDtype)):  # categorical data type
        if not isinstance(dtype, pd.CategoricalDtype):
            pd.CategoricalDtype(dtype)  # check it's not raising
        else:
            dtype = dtype.categories.tolist()
        if not all(any(isinstance(_, d.value) for d in ColumnDtype) for _ in dtype):
            raise ValueError(f"{prefix} invalid data type(s) in categorical data")
        if len(set(type(_) for _ in dtype)) != 1:
            raise ValueError(f"{prefix}  categorical values must all be of the same "
                             f"type, found: {set(type(_) for _ in dtype)}")
        if bounds_are_given:
            raise ValueError(f"{prefix} bounds cannot be provided with "
                             f"categorical data type")
        if default_is_given and default not in dtype:
            raise ValueError(f"{prefix} default is not in the list of possible values")
        pd.CategoricalDtype(dtype)  # check it's not raising
        return

    # handle non-categorical data with a base dtype:
    try:
        py_dtype = ColumnDtype[dtype].value[0]
    except KeyError:
        raise ValueError(f"{prefix} invalid data type: {dtype}")

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
            if val is None:
                pass
            elif py_dtype == float and isinstance(val, int):
                pass
            elif not isinstance(val, py_dtype):
                raise ValueError(f"{prefix} bound {str(val)} must be of "
                                 f"type {dtype}")
        if max_val is not None and min_val is not None and max_val <= min_val:
            raise ValueError(f'{prefix} min. bound must be lower than '
                             f'max. bound')

    # check default value:
    if default_is_given:
        # type promotion (int is a valid float):
        if py_dtype == float and isinstance(default, int):
            pass
        elif not isinstance(default, py_dtype):
            raise ValueError(f"default must be of type {dtype}")
