"""
Created on 16 Feb 2018

@author: riccardo
"""
import warnings
import pytest

import numpy as np
from openquake.hazardlib.imt import IMT, SA
from openquake.hazardlib.gsim.base import GMPE
from openquake.hazardlib.gsim.base import registry
from toml.decoder import TomlDecodeError

from egsim.smtk.registry import (
    gsim_names,
    gsim,
    imt,
    intensity_measures_defined_for,
    ground_motion_properties_required_by,
    gsim_name,
    sa_limits,
    SmtkError
)


def test_gsim_special_case():
    """Simple test case for a model whose name and class name differ"""

    model_name = 'Idriss2014NSHMPUpper'
    model_class = registry[model_name]  # 'NSHMP2014'
    # assert gsim works:
    gsim(model_name)
    # assert that calling gsim with the class name doesn't:
    with pytest.raises((SmtkError, TomlDecodeError)) as kerr:  # noqa
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
        assert len(w) > 45  # hacky check as well


def test_load_model_with_deprecation_warnings():
    model = 'AkkarEtAl2013'
    # gsim(model)
    with pytest.raises(SmtkError) as exc:
        gsim(model)
    gsim_ = gsim(model, raise_deprecated=False)
    assert isinstance(gsim_, GMPE)
    # now check that the behavior is the same if we set a warning filter beforehand:
    with warnings.catch_warnings(record=True) as w:
        with pytest.raises(SmtkError) as exc:
            gsim(model)
        gsim_ = gsim(model, raise_deprecated=False)
        assert isinstance(gsim_, GMPE)
        assert len(w) == 0  # no warnings captured in oq 3.12.1 (previously len == 1)


def test_gsim_name_1to1_relation():
    with warnings.catch_warnings(record=False) as w:
        warnings.simplefilter('ignore')
        for model_name in gsim_names():
            try:
                model = gsim(model_name, raise_deprecated=False)
            except SmtkError as exc:
                continue
            model_name_back = gsim_name(model)
            try:
                assert model_name == model_name_back
            except AssertionError:
                # FIXME: see with Graeme how to deal with this:
                #  inputting an instance of `ESHM20CratonShallowMidStressMidAtten`
                #  in smtlk methods will reutrn 'KothaEtAl2020ESHM20' as model name
                #  This is because the former is an alias to the latter without args
                #  (set alias with default args would work)
                assert model_name, model_name_back in {
                    ('ESHM20CratonShallowMidStressMidAtten', 'KothaEtAl2020ESHM20')
                }


def read_gsims(raise_deprecated=True):
    count, ok = 0, 0
    for model in registry:
        count += 1
        try:
            gsim_ = gsim(model, raise_deprecated=raise_deprecated)
            ok += 1
        except SmtkError as exc:
            continue
    return count, ok


def test_requires():
    for g_name in gsim_names():
        try:
            gsim_inst = gsim(g_name)
        except SmtkError:
            continue
        res = intensity_measures_defined_for(gsim_inst)
        assert isinstance(res, frozenset)
        assert not res or all(isinstance(_, str) for _ in res)
        res = ground_motion_properties_required_by(gsim_inst)
        assert isinstance(res, frozenset)
        assert not res or all(isinstance(_, str) for _ in res)


def test_imt_as_float_is_converted_to_sa():
    for val in [0, .0, 1, 1.]:
        assert isinstance(imt(val), IMT)
        assert imt(val) == SA(val)
    for val in [np.nan, "abc"]:
        with pytest.raises(SmtkError):
            imt(val)
    with pytest.raises(SmtkError):
        imt('SA(0.1a)')
    with pytest.raises(SmtkError):
        imt('SA("0.1a")')


def test_sa_limits():
    with warnings.catch_warnings(record=False):
        warnings.simplefilter('ignore')
        for model_name in gsim_names():
            try:
                model = gsim(model_name, raise_deprecated=False)
            except SmtkError as exc:
                continue
            lims = sa_limits(model)
            assert lims is None or (len(lims) == 2 and lims[0] < lims[1])
