'''
Created on 2 Jun 2018

@author: riccardo
'''
import unittest
import os
import json

import yaml
from yaml import YAMLError
import numpy as np
import mock
import pytest

from egsim.core.utils import EGSIM, yaml_load as original_yaml_load
from egsim.views import TrellisView
from egsim.forms.forms import BaseForm, TrellisForm
from egsim.core.smtk import get_trellis, _default_periods_for_spectra


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

GSIM, IMT = 'gsim', 'imt'

# create a yaml dict that will mock yaml_load (from file)
with open(os.path.join(DATA_DIR, 'trellis_dist.yaml')) as fpt:
    yamldict = yaml.safe_load(fpt)


# @mock.patch('egsim.core import yaml_load', side_effect=yaml_load)
def test_trellis_load():
    # https://stackoverflow.com/a/3166985
    with pytest.raises(YAMLError) as context:  # @UndefinedVariable
        TrellisForm.load(os.path.join(DATA_DIR, 'trellis1'))
    with pytest.raises(YAMLError) as context:  # @UndefinedVariable
        TrellisForm.load(os.path.join(DATA_DIR, 'trellis_malformed.yaml'))
    with pytest.raises(YAMLError) as context:  # @UndefinedVariable
        TrellisForm.load(os.path.join(DATA_DIR, 'trellis_filenot_found.yaml'))


def get_form(**overrides):
    tform = TrellisForm(data=dict(yamldict, **overrides))
    assert tform.is_valid()
    return tform


@pytest.mark.django_db
@pytest.mark.parametrize('trellis_type', ['d', 'ds'])
def test_trellis_dist(trellis_type):
    '''test trellis distance and distance stdev'''
    form = get_form(plot_type=trellis_type)
    input_ = form.cleaned_data
    result = get_trellis(dict(input_))  # copy dict: some keys might be popped in the func.
    assert sorted(result.keys()) == ['figures', 'xlabel', 'xvalues']
    xvalues = result['xvalues']
    assert len(xvalues) == len(input_['distance']) + 1  # FIXME: should be len(distance)!!!
    figures = result['figures']
    assert len(figures) == len(input_['magnitude']) * len(input_['imt'])
    for fig in figures:
        yvalues = fig['yvalues']
        assert all(len(yval) == len(xvalues) for yval in yvalues.values())
        assert sorted(yvalues.keys()) == sorted(input_['gsim'])


@pytest.mark.django_db
@pytest.mark.parametrize('trellis_type', ['m', 'ms'])
def test_trellis_mag(trellis_type):
    '''test trellis magnitude and magnitude stdev'''
    form = get_form(plot_type=trellis_type)
    input_ = form.cleaned_data
    result = get_trellis(dict(input_))  # copy dict: some keys might be popped in the func.
    assert sorted(result.keys()) == ['figures', 'xlabel', 'xvalues']
    xvalues = result['xvalues']
    assert len(xvalues) == len(input_['magnitude'])
    figures = result['figures']
    assert len(figures) == len(input_['distance']) * len(input_['imt'])
    for fig in figures:
        yvalues = fig['yvalues']
        assert all(len(yval) == len(xvalues) for yval in yvalues.values())
        assert sorted(yvalues.keys()) == sorted(input_['gsim'])


@pytest.mark.django_db
@pytest.mark.parametrize('trellis_type', ['s', 'ss'])
def test_trellis_spec(trellis_type):
    '''test trellis magnitude-distance spectra and magnitude-distance stdev'''
    form = get_form(plot_type=trellis_type)
    input_ = form.cleaned_data
    result = get_trellis(dict(input_))  # copy dict: some keys might be popped in the func.
    assert sorted(result.keys()) == ['figures', 'xlabel', 'xvalues']
    xvalues = result['xvalues']
    assert len(xvalues) == len(_default_periods_for_spectra())
    figures = result['figures']
    assert len(figures) == len(input_['distance']) * len(input_['magnitude'])
    for fig in figures:
        yvalues = fig['yvalues']
        assert all(len(yval) == len(xvalues) for yval in yvalues.values())
        assert sorted(yvalues.keys()) == sorted(input_['gsim'])


@pytest.mark.django_db
def test_error(areequal):
    '''tests a special case where we supply a deprecated gsim (not in EGSIM
    list)'''
    params = {"gsim": ["AkkarEtAl2013", "AkkarEtAlRepi2014"],
              "imt": ["PGA", "PGV"], "magnitude": "3:4", "distance": "10:12", "dip": "60",
              "aspect": "1.5", "rake": "0.0", "ztor": "0.0", "strike": "0.0", "msr": "WC1994",
              "initial_point": "0 0", "hypocentre_location": "0.5 0.5", "vs30": "760.0",
              "vs30_measured": True, "line_azimuth": "0.0", "plot_type": "ds"}
    form = TrellisForm(params)
    assert not form.is_valid()
    err_json = json.loads(form.errors.as_json())
    expected_err_json = {"gsim": [{"message": "Select a valid choice. "
                                   "AkkarEtAl2013 is not one of the available "
                                   "choices.", "code": "invalid_choice"}]}
    assert areequal(err_json, expected_err_json)


@pytest.mark.django_db
def test_empty_gsim():
    '''tests a special case whereby a GSIM is empty (this case raised before a PR to
    smtk repository)'''
    params = {"gsim": ["AbrahamsonEtAl2014", "AbrahamsonEtAl2014NSHMPLower",
                       "AbrahamsonEtAl2014NSHMPMean", "AbrahamsonEtAl2014NSHMPUpper",
                       "AbrahamsonEtAl2014RegCHN", "AbrahamsonEtAl2014RegJPN",
                       "AbrahamsonEtAl2014RegTWN", "AkkarBommer2010SWISS01",
                       "AkkarBommer2010SWISS04", "AkkarBommer2010SWISS08",
                       "AkkarEtAlRepi2014"],
              "imt": ["PGA", "PGV"], "magnitude": "3:4", "distance": "10:12", "dip": "60",
              "aspect": "1.5", "rake": "0.0", "ztor": "0.0", "strike": "0.0", "msr": "WC1994",
              "initial_point": "0 0", "hypocentre_location": "0.5 0.5", "vs30": "760.0",
              "vs30_measured": True, "line_azimuth": "0.0", "plot_type": "ds"}
    form = TrellisForm(params)
    assert form.is_valid()
    result = get_trellis(form.cleaned_data)
    figures = result['figures']
    assert figures[1]['yvalues']['AkkarBommer2010SWISS01'] == []
