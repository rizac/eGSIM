from datetime import datetime
import os
from enum import Enum
from typing import Union, Any
import yaml


class Prop(str, Enum):
    """Properties implemented in the YAML. NOTE: each item is also a `str`
    (i.e., properties.ffname == "flatfile_name")
    """
    dtype = 'dtype'
    bounds = 'bounds'
    default = 'default'
    choices = 'choices'
    help = 'help'
    ffname = 'flatfile_name'


default_dtype = 'float'

dtype_cast_function = {
    default_dtype: float,
    # datetime: use ISO formatted strings (for JSON):
    'datetime': lambda _: (_ if isinstance(_, datetime) else
                           datetime.fromisoformat(_)).isoformat(),
    'int': int,
    'bool': bool,
    'str': str,
}


DEFAULT_FILE_PATH = os.path.splitext(__file__)[0] + ".yaml"


def read_model_params(yaml_file_path: str = DEFAULT_FILE_PATH) -> dict[str, dict]:
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
                    ffname = props.get(Prop.ffname, None)
                    if ffname is not None:
                        assert ffname not in done_ff_names, "%s not unique: %s " % \
                                                            (Prop.ffname, ffname)
                        done_ff_names.add(ffname)

                    all_params[param_type + "." + param_name] = props

                except AssertionError as err:
                    raise ValueError('Field "%s" error: %s' % (param_name, str(err))) \
                        from None
    return all_params


def _validate_properties(props: Union[dict[str, Any], None]) -> dict:

    props = props or {}

    unknown_keys = set(props) - set(Prop)
    assert not unknown_keys, 'Unknown property/ies: %s' % str(unknown_keys)

    dtype = props.get(Prop.dtype, default_dtype)
    assert dtype in dtype_cast_function.keys(), 'Unrecognized type "%s"' % dtype

    key = Prop.bounds  # bounds
    if key in props:
        bounds = props[key]
        assert isinstance(bounds, list) and len(bounds) == 2, \
            "%s must be a 2-element list" % key
        nonfinite = -float('inf'), float('nan'), float('inf')
        for i, val in enumerate(bounds):
            if val is not None:
                val = dtype_cast_function[dtype](val)
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

    key = Prop.default
    if key in props:
        props[key] = dtype_cast_function[dtype](props[key])

    key = Prop.choices  # choices
    if key in props:
        props[key] = [dtype_cast_function[dtype](_) for _ in props[key]]
        if Prop.default in props:
            assert props[Prop.default] in props[key], \
                '"%s" value not in "%s"' % (Prop.default, key)

    return props


# script for checking the parameters implemented in the YAML file:


def _check_registered_file():
    # put here all imports not needed by the module:
    from openquake.hazardlib.gsim import get_available_gsims
    import os, yaml, inspect, sys
    # import pandas as pd
    # from itertools import chain
    # from collections import defaultdict

    registered_params = read_model_params()
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

    sys.exit(ret)


if __name__ == "__main__":
    _check_registered_file()