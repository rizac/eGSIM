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
    with open(_ff_metadata_path) as _:
        dic = yaml.safe_load(_)
    yaml_names = set(dic)

    c_type, c_alias = {}, {}
    c_dtype, c_required, c_default, c_help, c_bounds = {}, [], {}, {}, {}
    read_column_metadata(ctype=c_type, dtype=c_dtype, required=c_required,
                         default=c_default, help=c_help, alias=c_alias,
                         bounds=c_bounds)

    # c_type should contain exactly the same keys as the YAML dict:
    assert not (set(c_type) ^ yaml_names), \
        'Missing mandatory key "type" for these columns: ' \
        f'{set(c_type) ^ set(yaml_names)}. Please check YAML file'

    # check aliases
    all_aliases = set()
    for name  in c_type:
        assert name not in all_aliases, f'Column name "{name}" ' \
                                        'already defined as alias'
        all_aliases.add(name)
        aliases = c_alias[name]
        assert isinstance(aliases, set), f"Column '{name}' aliases should be " \
                                         f"a Python set, check code"
        assert all(isinstance(_, str) for _ in aliases), f"Column '{name}' " \
                                                         f"aliases should be " \
                                                         f"a Python set of " \
                                                         f"strings, check code"
        assert name in aliases, f'Columns "{name}" is not defined also in the ' \
                                f'`alias` set, check code'
        aliases = aliases - {name}
        assert not (aliases & set(c_type)), "Aliases already defined as column " \
                                           f"name: {aliases & set(c_type)}. " \
                                          "Check YAML"
        assert not (aliases & all_aliases), "Duplicated alias names:, " \
                                          f"{aliases & all_aliases}. " \
                                          "Check YAML"
        all_aliases.update(aliases)

    assert all_aliases == set(c_alias), "Aliases mismatch: " \
                                        f"{all_aliases ^ set(c_alias)}. " \
                                        "check code"

    required_not_defined = [_ for r in c_required
                            for _ in r if _ not in (all_aliases | yaml_names)]
    if required_not_defined:
        raise ValueError(f'These required columns are not defined, some internal'
                         f'error occurred: {",".join(required_not_defined)}. ' 
                         'Please check YAML file')

    # Check column properties within itself (no info on other columns required):
    for c, t in c_type.items():
        props = {'ctype': t, 'name': c}
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

    alias_is_missing= alias == {name}

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


# def check_column_metadata(column: dict[str, Any]):
#     """checks the Column metadata dict issued from the YAML flatfile"""
#     # convert type to corresponding Enum:
#     try:
#         column['type'] = ColumnType[column['type']]
#     except KeyError:
#         raise ValueError(f"Invalid type: {column['type']}")
#
#     if column['type'] == ColumnType.intensity_measure.name and 'alias' in column:
#         raise ValueError(f"Intensity measure columns cannot have an alias")
#
#     # perform some check on the data type consistencies:
#     bounds_are_given = 'bounds' in column
#     default_is_given = 'default' in column
#
#     # check dtype null and return in case:
#     if 'dtype' not in column:
#         if bounds_are_given or default_is_given:
#             raise ValueError(f"With `dtype` null or missing, metadata cannot have "
#                              f"the keys `default` and `bounds`")
#         return column
#
#     dtype = column['dtype']
#
#     # handle categorical data:
#     if isinstance(dtype, (list, tuple, pd.CategoricalDtype)):  # categorical data type
#         if not isinstance(dtype, pd.CategoricalDtype):
#             pd.CategoricalDtype(dtype)  # check it's not raising
#         else:
#             dtype = dtype.categories.tolist()
#         if not all(any(isinstance(_, d.value) for d in ColumnDtype) for _ in dtype):
#             raise ValueError(f"Invalid data type(s) in provided categorical data")
#         if len(set(type(_) for _ in dtype)) != 1:
#             raise ValueError(f"Categorical values must all be of the same type, found: "
#                              f"{set(type(_) for _ in dtype)}")
#         if bounds_are_given:
#             raise ValueError(f"bounds cannot be provided with "
#                              f"categorical data type")
#         if default_is_given and column['default'] not in dtype:
#             raise ValueError(f"default is not in the list of possible values")
#         pd.CategoricalDtype(dtype)  # check it's not raising
#         return
#
#     # handle non-categorical data with a base dtype:
#     try:
#         py_dtype = ColumnDtype[dtype].value[0]
#     except KeyError:
#         raise ValueError(f"Invalid data type: {dtype}")
#
#     # check bounds:
#     if bounds_are_given:
#         bounds = column['bounds']
#         symbols = {"<", ">", ">=", "<="}
#         assert (k in {"<", ">", ">=", "<="} for k in bounds), \
#             f"Some bound symbols not in {str(symbols)}, check flatfile Python" \
#             f"and flatfile metadata YAML file"
#         if len(bounds) > 2:
#             raise ValueError(f'Error in column "{column}" too many bounds: '
#                              f'{list(bounds)}')
#         if (">" in bounds and ">=" in bounds) or \
#                 ("<" in bounds and "<=" in bounds):
#             raise ValueError(f'Error in column "{column}" invalid bounds combination: '
#                              f'{list(bounds)}')
#         max_val = bounds.get("<", bounds.get("<=", None))
#         min_val = bounds.get(">", bounds.get(">=", None))
#         for val in [max_val, min_val]:
#             if val is None:
#                 pass
#             elif py_dtype == float and isinstance(val, int):
#                 pass
#             elif not isinstance(val, py_dtype):
#                 raise ValueError(f"bound {str(val)} must be of type {dtype}")
#         if max_val is not None and min_val is not None and max_val <= min_val:
#             raise ValueError(f'Error in column "{column}" invalid bounds value: '
#                              f'minimum must be lower than maximum')
#
#     # check default value:
#     if default_is_given:
#         default = column['default']
#         # type promotion (int is a valid float):
#         if py_dtype == float and isinstance(column['default'], int):
#             pass
#         elif not isinstance(default, py_dtype):
#             raise ValueError(f"default must be of type {dtype}")
#

# def parse_bounds_str(bounds_string, py_dtype):
#     bounds = []
#     for chunk in bounds_string.split(','):
#         chunk = chunk.strip()
#         symbol = chunk[:2] if chunk[:2] in ('>=', '<=') else chunk[:1]
#         assert symbol in ('>', '<', '>=', '<='), 'comparison operator should be ' \
#                                                  '<, >, <= or >='
#         try:
#             value = yaml.safe_load(chunk[len(symbol):])
#         except Exception:
#             raise ValueError(f'Invalid bound: {chunk[len(symbol):]}')
#         if py_dtype is float and isinstance(value, int):
#             value = float(value)
#         if not isinstance(value, py_dtype):
#             raise ValueError(f'Invalid bound type (expected {str(py_dtype)}): '
#                              f'{str(value)}')
#         bounds.append([symbol, value])
#     return bounds
