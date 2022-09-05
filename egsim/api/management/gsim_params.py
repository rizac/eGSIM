"""This module handles registered Gsim parameters, some of which correspond to
a flatfile field. See the associated YAML file for details
"""
from datetime import date as py_date, datetime as py_datetime
import os
from enum import Enum
from typing import Union, Any
import yaml


class propname(str, Enum):  # noqa
    """property names implemented in the YAML. NOTE: each item is also a `str`
    (i.e., propname.ffname == "flatfile_name")
    """
    dtype = 'dtype'
    bounds = 'bounds'
    default = 'default'
    help = 'help'
    ffname = 'flatfile_name'


# Provide a class that is callable like Python builtin types for datetime objects:
# `datetime(obj) -> python datetime`, where `obj` is a datetime, date or iso formatted
# string. IMPORTANT: Any custom type class like this one must have the name equals
# one of the supported dtypes documented in the YAML (so, e.g., `class dtime` would be
# wrong)
def datetime(obj):  # noqa
    if isinstance(obj, py_datetime):
        return obj
    if isinstance(obj, py_date):
        return py_datetime(year=obj.year, month=obj.month, day=obj.day)
    return py_datetime.fromisoformat(str(obj))


# SUPPORTED DATA TYPES. Each element must be a callable class producing elements
# of the desired data type. The first element must be considered the default dtye
dtypes = [float, int, str, bool, datetime]


DEFAULT_FILE_PATH = os.path.splitext(__file__)[0] + ".yaml"


def read_gsim_params(yaml_file_path: str = DEFAULT_FILE_PATH) -> dict[str, dict]:
    """Return the all models parameter names and their properties from the given
    YAML file. The keys of the dict will be "flattened" to strings of the form:
    <PARAMETER_TYPE>.<PARAMETER_NAME>
    whereas the values are the model properties as implemented in the YAML file
    (after some validation routine).
    You can use `key.split(".", 1)` to get property type and name separately:
    The parameter type is the OpenQuake Attribute name denoting the property
    type (e.g. "REQUIRES_DISTANCE")
    """
    all_params = {}
    done_ff_names = set()
    with open(yaml_file_path) as fpt:
        root_dict = yaml.safe_load(fpt)
        for param_type, params in root_dict.items():
            for param_name, props in params.items():
                try:
                    props = _validate_properties(props)
                    ffname = props.get(propname.ffname, None)
                    if ffname is not None:
                        assert ffname not in done_ff_names, "%s not unique: %s " % \
                                                            (propname.ffname, ffname)
                        done_ff_names.add(ffname)

                    all_params[param_type + "." + param_name] = props

                except AssertionError as err:
                    raise ValueError('Field "%s" error: %s' % (param_name, str(err))) \
                        from None
    return all_params


def _validate_properties(props: Union[dict[str, Any], None]) -> dict:

    props = props or {}

    unknown_keys = set(props) - set(propname)
    assert not unknown_keys, 'Unknown property/ies: %s' % str(unknown_keys)

    dtype = props.get(propname.dtype, dtypes[0].__name__)
    categories = None
    if not isinstance(dtype, (list, tuple)):
        for dtyp in dtypes:
            if dtyp.__name__ == dtype:
                dtype = dtyp
                break
        else:
            raise AssertionError('Unrecognized `dtype` "%s"' % dtype)
    else:
        dtype, categories = _check_dtype_categorical(dtype)

    props.setdefault(propname.dtype, dtype.__name__)

    key = propname.bounds  # bounds
    if key in props:
        bounds = props[key]
        assert isinstance(bounds, list) and len(bounds) == 2, \
            "%s must be a 2-element list" % key
        nonfinite = -float('inf'), float('nan'), float('inf')
        for i, val in enumerate(bounds):
            if val is not None:
                val = dtype(val)
                invalid = nonfinite[-1] if i == 0 else nonfinite[0]
                assert val != invalid, '%s[%d] must be != %s' % (key, i, str(invalid))
                if val in nonfinite:
                    val = None
                bounds[i] = val
        if all(_ is None for _ in bounds):
            props.pop(key)
        elif all(_ is not None for _ in bounds):
            assert bounds[0] < bounds[1], '"%s" error: %s must be < %s' % \
                                          (key, str(bounds[0]), str(bounds[1]))

    key = propname.default
    if key in props:
        props[key] = dtype(props[key])
        if categories is not None and props[key] not in categories:
            assert props[propname.default] in props[key], \
                '"%s" value not in "%s"' % (propname.default, key)

    return props


def _check_dtype_categorical(categories):
    assert isinstance(categories, (list, tuple)), '`dtype` must be given as ' \
                                                  'string or list/tuple, not ' \
                                                  '%s' % type(categories).__name__
    pyclasses = set(type(_) for _ in categories)
    assert len(pyclasses) == 1, '`dtype` categories are not of the same class: ' \
                                '%s' % ', '.join(_.__name__ for _ in dtypes)
    pyclass = next(iter(pyclasses))
    # Check that the Python class is supported. Note that we cannot simply cast
    # because it is not 1-1: eg. bool('abc') works whereas 'abc' should be 'str'.
    # Also, data is usually already casted (YAML and JSON do it)
    for dtype in dtypes:
        if pyclass.__name__ == dtype.__name__:
            try:
                categories = [dtype(_) for _ in categories]
            except Exception as exc:
                raise AssertionError("unable to cast all `dtype` categories to "
                                     "%s: %s" % (dtype.__name__, str(exc)))
            return dtype, categories

    raise AssertionError('`dtype` categories class (%s) could not be inferred '
                         'from %s' % (str(pyclass),
                                      ', '.join(_.__name__ for _ in dtypes)))


# script for checking the parameters implemented in the YAML file:


def _check_registered_file():
    # put here all imports not needed by the module:
    from openquake.hazardlib.gsim import get_available_gsims
    import os, yaml, inspect, sys
    # import pandas as pd
    # from itertools import chain
    # from collections import defaultdict

    registered_params = read_gsim_params()
    oq_atts = set(_.split('.', 1)[0] for _ in registered_params)
    already_done = set()
    ret = 0
    for gsim_name, gsim in get_available_gsims().items():
        if inspect.isabstract(gsim):
            continue
        gsim_warnings = []
        # needs_args = False
        # gsim_inst = None
        for oq_att in oq_atts:
            for param in getattr(gsim, oq_att) or []:
                key = "%s.%s" % (oq_att, param)
                if key in already_done:
                    continue
                already_done.add(key)
                if key not in registered_params:
                    ret = 1
                    print('Warning: %s not defined in YAML' % key)
                else:
                    registered_params.pop(key)

    for key in registered_params:
        ret = 1
        print('Warning: %s in YAML not defined as OpenQuake '
              'attribute' % key)

    if ret == 0:
        print('YAML file is ok')

    return ret


if __name__ == "__main__":
    import sys
    sys.exit(_check_registered_file())