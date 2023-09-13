"""
Created on 16 Feb 2018

@author: riccardo
"""
from openquake.hazardlib.gsim.base import gsim_aliases
from typing import Any, Union

import yaml
import pandas as pd

from egsim.smtk import get_gsim_names, get_gsim_instance, \
    get_imts_defined_for, get_distances_required_by, \
    get_rupture_params_required_by, get_sites_params_required_by, get_gsim_name,\
    OQDeprecationWarning

# from egsim.smtk.flatfile import (ColumnType, ColumnDtype, read_column_metadata,
#                                  _ff_metadata_path)

def test_me():
    pass

_gsim_aliases_ = {v: k for k, v in gsim_aliases.items()}

def test_requires():
    """Test the flatfile metadata"""
    count, ok = 0, 0
    for model in get_gsim_names():
        count += 1
        try:
            ok += 1
            gsim = get_gsim_instance(model)
            model_name_back = get_gsim_name(gsim)
            assert model == model_name_back
        except (TypeError, KeyError, IndexError, OQDeprecationWarning) as exc:
            continue
        for func in [get_distances_required_by,
                get_rupture_params_required_by,
                get_sites_params_required_by,
                get_imts_defined_for]:
            res = func(gsim)
            assert isinstance(res, (set, frozenset))
            assert not res or all(isinstance(_, str) for _ in res)
    # simple check to see if get_gsim_instance did not raise too much:
    assert count > 700 and ok > 650