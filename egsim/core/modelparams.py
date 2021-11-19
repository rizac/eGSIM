from datetime import datetime
from typing import Union, Any
import yaml

# def dtypes_defaults_parse_dates() -> tuple[dict, dict, list]:
#     dtypes, parse_dates, defaults = {}, [], {}
#     # query all params with flatfile_name not null:
#     # if dtype = datetime, add the flatfile name to parse_dates,
#     # otherwise, add name -> dtype to dtypes
#     # if the field has a default, add name -> default to defaults
#     return tuple({}, {}, [])


default_type = 'float'

dtype_cast_function = {
    default_type: float,
    # datetime: use ISO formatted strings (for JSON):
    'datetime': lambda _: (_ if isinstance(_, datetime) else
                           datetime.fromisoformat(_)).isoformat(),
    'int': int,
    'bool': bool,
    'str': str,
}


# Possible property names defined for each Parameter (ORDER IS IMPORTANT DO NOT CHANGE):
prop_names = ('dtype', 'bounds', 'default', 'choices', 'help', 'flatfile_name',)


def read_param_props(yaml_file_path: str) -> dict[str, dict]:
    """Return the all models parameter names and their properties from the given
    YAML file. The keys of the dict will be strings in the form:
    <PARAMETER_TYPE>.<PARAMETER_NAME>
    You can use `key.split(".", 1)` to get property type and name separately
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
                    help_s, ffname_s = prop_names[4], prop_names[5]
                    props = validate_properties(props)
                    ffname = props.get(ffname_s, None)
                    if ffname is not None:
                        assert ffname not in done_ff_names, "%s not unique: %s " % \
                                                            (ffname_s, ffname)
                        done_ff_names.add(ffname)

                    all_params[param_type + "." + param_name] = props

                except AssertionError as err:
                    raise ValueError('Field "%s" error: %s' % (param_name, str(err))) \
                        from None
    return all_params


def validate_properties(props: Union[dict[str, Any], None]) -> dict:

    props = props or {}

    unknown_keys = set(props) - set(prop_names)
    assert not unknown_keys, 'Unknown property/ies: %s' % str(unknown_keys)

    key = prop_names[0]  # data_type
    dtype = props.get(key, default_type)
    assert dtype in dtype_cast_function.keys(), 'Unrecognized type "%s"' % dtype

    key = prop_names[1]  # bounds
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

    key_d = prop_names[2]  # default
    if key_d in props:
        props[key_d] = dtype_cast_function[dtype](props[key_d])

    key_c = prop_names[3]  # choices
    if key_c in props:
        props[key_c] = [dtype_cast_function[dtype](_) for _ in props[key_c]]
        if key_d in props:
            assert props[key_d] in props[key_c], \
                '"%s" value not in "%s"' % (key_d, key_c)

    return props


# script for checking the parameters implemented in the YAML file:


def _check_registered_file():
    # put here all imports not needed by the module:
    from openquake.hazardlib.gsim import get_available_gsims
    import os, yaml, inspect, sys
    # import pandas as pd
    # from itertools import chain
    # from collections import defaultdict

    fle = os.path.join(os.path.dirname(__file__), 'modelparams.yaml')
    registered_params = read_param_props(fle)
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