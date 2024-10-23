"""
Created on 16 Feb 2018

@author: riccardo
"""
from openquake.hazardlib.gsim.base import gsim_aliases, GMPE
import warnings
import pytest

import numpy as np
from openquake.hazardlib.imt import IMT, SA

from egsim.smtk.converters import convert_accel_units
from openquake.hazardlib.gsim.base import registry
from egsim.smtk import (registered_gsims, gsim, imt, \
                        intensity_measures_defined_for,
                        gsim_name)


_gsim_aliases_ = {v: k for k, v in gsim_aliases.items()}


def test_gsim_special_case():
    """simple test case for a model whose name and class name differ"""
    model_name = 'Idriss2014NSHMPUpper'
    model_class = registry[model_name]  # 'NSHMP2014'
    # assert gsim works:
    model_instance = gsim(model_name)
    # assert that calling gsim with the class name doesn't:
    with pytest.raises(KeyError) as kerr:
        gsim(model_class.__name__)


def test_load_models():
    """Test the flatfile metadata"""

    # raise DeprecationWarnings (all other warnings behave as default):
    with warnings.catch_warnings(record=True) as w:
        count, ok = read_gsims()
        # hacky check to see that everything was ok:
        assert count > ok > 650
        # warnings might not be unique, get the unique ones:
        w = set(str(_) for _ in w)
        assert len(w) > 50  # hacky check as well


def test_load_model_with_deprecation_warnings():
    excs = (DeprecationWarning,)
    model = 'AkkarEtAl2013'
    # gsim(model)
    with pytest.raises(*excs) as exc:
        gsim(model)
    gsim_ = gsim(model, raise_deprecated=False)
    assert isinstance(gsim_, GMPE)
    # now check that the behavior is the same if we set a warning filter beforehand:
    with warnings.catch_warnings(record=True) as w:
        with pytest.raises(*excs) as exc:
            gsim(model)
        assert len(w) == 1
    with warnings.catch_warnings(record=True) as w:
        gsim(model, raise_deprecated=False)
        assert len(w) == 1
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('ignore')
        with pytest.raises(*excs) as exc:
            gsim(model)
        assert len(w) == 0
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter('ignore')
        gsim(model, raise_deprecated=False)
        assert len(w) == 0


def test_gsim_name_1to1_relation():
    excs = (TypeError, IndexError, KeyError, ValueError,
            FileNotFoundError, OSError, AttributeError)
    with warnings.catch_warnings(record=False) as w:
        warnings.simplefilter('ignore')
        for model in registered_gsims:
            try:
                gsim_ = gsim(model, raise_deprecated=False)
            except excs as exc:
                continue
            model_name_back = gsim_name(gsim_)
            assert model == model_name_back

    for model, cls in registered_gsims.items():
        if cls.superseded_by:
            asd = 9

def read_gsims(raise_deprecated=True, catch_deprecated=True):
    count, ok = 0, 0
    excs = (TypeError, IndexError, KeyError, ValueError,
            FileNotFoundError, OSError, AttributeError)
    if raise_deprecated:
        excs += (DeprecationWarning, )
    # errors = [TypeError, KeyError, IndexError]
    # if catch_deprecated:
    #     errors.append(OQDeprecationWarning)
    # errors = tuple(errors)
    for model in registry:
        count += 1
        try:
            gsim_ = gsim(model, raise_deprecated=raise_deprecated)
            ok += 1
        except excs as exc:
            continue
    return count, ok


def test_requires():
    for gsim_cls in registry.values():
        res = intensity_measures_defined_for(gsim_cls)
        assert isinstance(res, frozenset)
        assert not res or all(isinstance(_, str) for _ in res)


def test_imt_as_float_is_converted_to_sa():
    for val in [0, .0, 1, 1.]:
        assert isinstance(imt(val), IMT)
        assert imt(val) == SA(val)
    for val in [np.nan, "abc"]:
        with pytest.raises(KeyError):
            imt(val)
    with pytest.raises(ValueError):
        imt('SA(0.1a)')
    with pytest.raises(ValueError):
        imt('SA("0.1a")')


# legacy code and relative tests (convert acceleration units). See notes function below

def test_convert_accel_units():
    """test convert accel units"""
    from scipy.constants import g
    for m_sec in ["m/s/s", "m/s**2", "m/s^2"]:
        for cm_sec in ["cm/s/s", "cm/s**2", "cm/s^2"]:
            assert convert_accel_units(1, m_sec, cm_sec) == 100
            assert convert_accel_units(1, cm_sec, m_sec) == .01
            assert convert_accel_units(g, m_sec, "g") == 1
            assert convert_accel_units(g, cm_sec, "g") == .01
            assert convert_accel_units(1, "g", m_sec) == g
            assert convert_accel_units(1, "g", cm_sec) == g*100
            assert convert_accel_units(1, cm_sec, cm_sec) == 1
            assert convert_accel_units(1, m_sec, m_sec) == 1

    assert convert_accel_units(1, "g", "g") == 1
    with pytest.raises(ValueError):
        assert convert_accel_units(1, "gf", "gf") == 1
