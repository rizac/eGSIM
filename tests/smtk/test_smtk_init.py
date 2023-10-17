"""
Created on 16 Feb 2018

@author: riccardo
"""
from openquake.hazardlib.gsim.base import gsim_aliases, GMPE
import warnings
import pytest

from egsim.smtk.registry import (registered_gsim_names, gsim, registry, \
                                 imts_defined_for, distances_required_by, \
                                 rupture_params_required_by, site_params_required_by,
                                 gsim_name, GsimInitError)


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
    with pytest.raises(GsimInitError) as exc:
        gsim(model)
    gsim_ = gsim(model, raise_deprecated=False)
    assert isinstance(gsim_, GMPE)
    # now check that the behavior is the same if we set a warning filter beforehand:
    for ignore_warnings in [True, False]:
        with warnings.catch_warnings(record=True) as w:
            if ignore_warnings:
                warnings.simplefilter('ignore')
            with pytest.raises(GsimInitError) as exc:
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
            model_name_back = gsim_name(gsim_)
            if model == 'Boore2015NGAEastA04':
                asd = 9
            assert model == model_name_back
        except GsimInitError as exc:
            continue


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
        except GsimInitError as exc:
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


# this function is not longer part of the lib, moved here
# in case needed in the future:
import numpy as np
from scipy.constants import g


def convert_accel_units(acceleration, from_, to_='cm/s/s'):  # noqa
    """
    Legacy function which can still be used to convert acceleration from/to
    different units

    :param acceleration: the acceleration (numeric or numpy array)
    :param from_: unit of `acceleration`: string in "g", "m/s/s", "m/s**2",
        "m/s^2", "cm/s/s", "cm/s**2" or "cm/s^2"
    :param to_: new unit of `acceleration`: string in "g", "m/s/s", "m/s**2",
        "m/s^2", "cm/s/s", "cm/s**2" or "cm/s^2". When missing, it defaults
        to "cm/s/s"

    :return: acceleration converted to the given units (by default, 'cm/s/s')
    """
    m_sec_square = ("m/s/s", "m/s**2", "m/s^2")
    cm_sec_square = ("cm/s/s", "cm/s**2", "cm/s^2")
    acceleration = np.asarray(acceleration)
    if from_ == 'g':
        if to_ == 'g':
            return acceleration
        if to_ in m_sec_square:
            return acceleration * g
        if to_ in cm_sec_square:
            return acceleration * (100 * g)
    elif from_ in m_sec_square:
        if to_ == 'g':
            return acceleration / g
        if to_ in m_sec_square:
            return acceleration
        if to_ in cm_sec_square:
            return acceleration * 100
    elif from_ in cm_sec_square:
        if to_ == 'g':
            return acceleration / (100 * g)
        if to_ in m_sec_square:
            return acceleration / 100
        if to_ in cm_sec_square:
            return acceleration

    raise ValueError("Unrecognised time history units. "
                     "Should take either ''g'', ''m/s/s'' or ''cm/s/s''")

