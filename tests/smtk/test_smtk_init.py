"""
Created on 16 Feb 2018

@author: riccardo
"""
from openquake.hazardlib.gsim.base import gsim_aliases, GMPE
import warnings
import pytest

from egsim.smtk import get_registered_gsim_names, get_gsim_instance, registry, \
    get_imts_defined_for, get_distances_required_by, \
    get_rupture_params_required_by, get_sites_params_required_by, get_gsim_name,\
    OQDeprecationWarning, convert_accel_units


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
    with pytest.raises(OQDeprecationWarning) as exc:
        get_gsim_instance(model)
    gsim = get_gsim_instance(model, raise_deprecated=False)
    assert isinstance(gsim, GMPE)
    # now check that the behavior is the same if we set a warning filter beforehand:
    for ignore_warnings in [True, False]:
        with warnings.catch_warnings(record=True) as w:
            if ignore_warnings:
                warnings.simplefilter('ignore')
            with pytest.raises(OQDeprecationWarning) as exc:
                get_gsim_instance(model)
            assert len(w) == 0
        with warnings.catch_warnings(record=True) as w:
            if ignore_warnings:
                warnings.simplefilter('ignore')
            gsim = get_gsim_instance(model, raise_deprecated=False)
            assert isinstance(gsim, GMPE)
            assert len(w) == 0 if ignore_warnings else 1


def read_gsims(raise_deprecated=True, catch_deprecated=True):
    count, ok = 0, 0
    errors = [TypeError, KeyError, IndexError]
    if catch_deprecated:
        errors.append(OQDeprecationWarning)
    errors = tuple(errors)
    for model in get_registered_gsim_names():
        count += 1
        try:
            gsim = get_gsim_instance(model, raise_deprecated=raise_deprecated)
            model_name_back = get_gsim_name(gsim)
            assert model == model_name_back
            ok += 1
        except errors as exc:
            continue
    return count, ok

def test_requires():
    for gsim_cls in registry.values():
        for func in [get_distances_required_by,
                get_rupture_params_required_by,
                get_sites_params_required_by,
                get_imts_defined_for]:
            res = func(gsim_cls)
            assert isinstance(res, frozenset)
            assert not res or all(isinstance(_, str) for _ in res)


    def test_convert_accel_units(self):
        """test convert accel units"""
        from scipy.constants import g
        for m_sec in ["m/s/s", "m/s**2", "m/s^2"]:
            for cm_sec in ["cm/s/s", "cm/s**2", "cm/s^2"]:
                self.assertEqual(convert_accel_units(1, m_sec, cm_sec), 100)
                self.assertEqual(convert_accel_units(1, cm_sec, m_sec), .01)
                self.assertEqual(convert_accel_units(g, m_sec, "g"), 1)
                self.assertEqual(convert_accel_units(g, cm_sec, "g"), .01)
                self.assertEqual(convert_accel_units(1, "g", m_sec), g)
                self.assertEqual(convert_accel_units(1, "g", cm_sec), g*100)
                self.assertEqual(convert_accel_units(1, cm_sec, cm_sec), 1)
                self.assertEqual(convert_accel_units(1, m_sec, m_sec),1)

        self.assertEqual(convert_accel_units(1, "g", "g"), 1)
        with self.assertRaises(ValueError):
            self.assertEqual(convert_accel_units(1, "gf", "gf"), 1)
