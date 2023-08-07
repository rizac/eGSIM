"""
Created on 16 Feb 2018

@author: riccardo
"""
from typing import Any

import yaml
import pandas as pd

# import numpy as np
from egsim.smtk import flatfile
from egsim.smtk.flatfile import (ColumnType, ColumnDtype, _ff_metadata_path,
                                 read_column_metadata)


def test_flatfile_metadata_from_yaml():
    c_type, c_dtype, c_required, c_default, c_help, _c_alias = \
        {}, {}, set(), {}, {}, {}
    read_column_metadata(type=c_type, dtype=c_dtype, required=c_required,
                         default=c_default, help=c_help, alias=_c_alias)

    if any(len(_) > len(c_type) for _ in [c_required, c_dtype, _c_alias, c_help,
                                          c_default]):
        raise ValueError('Some columns have missing type set. A default should be'
                         'set in the YAML file or in smtk.read_column_metadata')
    # invert dict:
    c_alias = {v: k for k,v in _c_alias.items()}
    if len(c_alias) != len(_c_alias):
        raise ValueError(f'Error in column metadata: some alias is duplicated '
                         f'(not unique), please check YAML file')
    if set(_c_alias) & set(c_type):
        raise ValueError(f'Error in metadata some alias is already defined as '
                         f'column name, please check YAML file')

    props = dict(c_type)
    for c, t in props.items():
        props = {}
        if c in c_dtype:
            props['dtype'] = c_dtype.pop(c)
        if c in c_required:
            props['required'] = c
            c_required.remove(c)
        if c in c_default:
            props['deault'] = c_default.pop(c)
        if c in c_help:
            props['help'] = c_help.pop(c)
        if c in set(c_alias.values()):
            props['dtype'] = c_dtype.pop(c)

    check_column_metadata(props)


def check_column_metadata(column: dict[str, Any]) -> dict[str, Any]:
    """checks the Column metadata dict issued from the YAML flatfile"""
    # convert type to corresponding Enum:
    try:
        column['type'] = ColumnType(column['type']).name
    except KeyError:
        raise ValueError(f"Invalid type: {column['type']}")

    if column['type'] == ColumnType.intensity_measure.name and 'alias' in column:
        raise ValueError(f"Intensity measure columns cannot have an alias")

    # perform some check on the data type consistencies:
    bounds_are_given = 'bounds' in column
    default_is_given = 'default' in column

    # check dtype null and return in case:
    if 'dtype' not in column:
        if bounds_are_given or default_is_given:
            raise ValueError(f"With `dtype` null or missing, metadata cannot have "
                             f"the keys `default` and `bounds`")
        return column

    dtype = column['dtype']

    # handle categorical data:
    if isinstance(dtype, (list, tuple)):  # categorical data type
        if not all(any(isinstance(_, d.value) for d in ColumnDtype) for _ in dtype):
            raise ValueError(f"Invalid data type(s) in provided categorical data")
        if len(set(type(_) for _ in dtype)) != 1:
            raise ValueError(f"Categorical values must all be of the same type, found: "
                             f"{set(type(_) for _ in dtype)}")
        if bounds_are_given:
            raise ValueError(f"bounds cannot be provided with "
                             f"categorical data type")
        if default_is_given and column['default'] not in dtype:
            raise ValueError(f"default is not in the list of possible values")
        pd.CategoricalDtype(dtype)  # check it's not raising
        return

    # handle non-categorical data with a base dtype:
    try:
        py_dtype = ColumnDtype[dtype].value[0]
    except KeyError:
        raise ValueError(f"Invalid data type: {dtype}")

    # check bounds:
    if bounds_are_given:
        try:
            parse_bounds_str(column['bounds'], py_dtype)
        except Exception as exc:
            raise ValueError(f"invalid bounds: {str(exc)}")


    # check default value:
    if default_is_given:
        default = column['default']
        # type promotion (int is a valid float):
        if py_dtype == float and isinstance(column['default'], int):
            pass
        elif not isinstance(default, py_dtype):
            raise ValueError(f"default must be of type {dtype}")


def parse_bounds_str(bounds_string, py_dtype):
    bounds = []
    for chunk in bounds_string.split(','):
        chunk = chunk.strip()
        symbol = chunk[:2] if chunk[:2] in ('>=', '<=') else chunk[:1]
        assert symbol in ('>', '<', '>=', '<='), 'comparison operator should be ' \
                                                 '<, >, <= or >='
        try:
            value = yaml.safe_load(chunk[len(symbol):])
        except Exception:
            raise ValueError(f'Invalid bound: {chunk[len(symbol):]}')
        if py_dtype is float and isinstance(value, int):
            value = float(value)
        if not isinstance(value, py_dtype):
            raise ValueError(f'Invalid bound type (expected {str(py_dtype)}): '
                             f'{str(value)}')
        bounds.append([symbol, value])
    return bounds
