"""
Created on 16 Feb 2018

@author: riccardo
"""
from openquake.hazardlib.gsim.base import gsim_aliases, GMPE
import warnings
import pytest
from openquake.hazardlib.imt import IMT, SA

from egsim.smtk import InvalidImt
from egsim.smtk.converters import convert_accel_units
from egsim.smtk.registry import (registered_gsim_names, registry, \
                                 imts_defined_for, distances_required_by, \
                                 rupture_params_required_by, site_params_required_by,
                                 gsim_name)
from egsim.smtk.validators import InvalidGsim, gsim, imt


_gsim_aliases_ = {v: k for k, v in gsim_aliases.items()}


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

    # don't raise DeprecationWarnings (all other warnings behave as default):
    with warnings.catch_warnings(record=True) as w3:
        count3, ok3 = read_gsims(False)
        # we have more model loaded but the overall models available is the same:
        assert ok3 > ok and count3 == count
        # warnings might not be unique, get the unique ones:
        w3 = set(str(_) for _ in w3)
        # we should have N more warning, and  N more successfully loaded models
        warnings_more = len(w3) - len(w)
        ok_models_more = ok3 - ok
        assert  warnings_more == ok_models_more

    # don't raise DeprecationWarnings (ignore all warnings overall):
    with warnings.catch_warnings(record=True) as w4:
        # don't raise DeprecationWarnings (all other warnings behave as default):
        warnings.simplefilter('ignore')
        count4, ok4 = read_gsims(False)
        # we have more model loaded but the overall models available is the same:
        assert ok4 == ok3 and count4 == count3
        # warnings might not be unique, get the unique ones:
        assert not w4


def test_load_model_with_deprecation_warnings():
    model = 'AkkarEtAl2013'
    with pytest.raises(InvalidGsim) as exc:
        gsim(model)
    gsim_ = gsim(model, raise_deprecated=False)
    assert isinstance(gsim_, GMPE)
    # now check that the behavior is the same if we set a warning filter beforehand:
    for ignore_warnings in [True, False]:
        with warnings.catch_warnings(record=True) as w:
            if ignore_warnings:
                warnings.simplefilter('ignore')
            with pytest.raises(InvalidGsim) as exc:
                gsim(model)
            assert len(w) == 0
        with warnings.catch_warnings(record=True) as w:
            if ignore_warnings:
                warnings.simplefilter('ignore')
            gsim_ = gsim(model, raise_deprecated=False)
            assert isinstance(gsim_, GMPE)
            assert len(w) == 0 if ignore_warnings else 1

def test_gsim_name_1to1_relation():
    for model in registered_gsim_names:
        try:
            gsim_ = gsim(model, raise_deprecated=False)
        except InvalidGsim as exc:
            continue
        model_name_back = gsim_name(gsim_)
        if model == 'Boore2015NGAEastA04':
            asd = 9
        assert model == model_name_back


def read_gsims(raise_deprecated=True, catch_deprecated=True):
    count, ok = 0, 0
    # errors = [TypeError, KeyError, IndexError]
    # if catch_deprecated:
    #     errors.append(OQDeprecationWarning)
    # errors = tuple(errors)
    for model in registered_gsim_names:
        count += 1
        try:
            gsim_ = gsim(model, raise_deprecated=raise_deprecated)
            ok += 1
        except InvalidGsim as exc:
            continue
    return count, ok

def test_requires():
    for gsim_cls in registry.values():
        for func in [distances_required_by,
                     rupture_params_required_by,
                     site_params_required_by,
                     imts_defined_for]:
            res = func(gsim_cls)
            assert isinstance(res, frozenset)
            assert not res or all(isinstance(_, str) for _ in res)


def test_imt_as_float_is_converted_to_sa():
    for val in [0, .0, 1, 1.]:
        assert isinstance(imt(val), IMT)
        assert imt(val) == SA(val)
    for val in [np.nan, np.inf, -np.inf, -1]:
        with pytest.raises(InvalidImt):
            imt(val)


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
