'''
Created on 2 Jun 2018

@author: riccardo
'''
import unittest
import os
import yaml
from yaml import YAMLError
import numpy as np
import mock

import pytest

from egsim.utils import EGSIM

from egsim.forms import BaseForm, TrellisForm
from egsim.core.trellis import compute, default_periods_for_spectra
from egsim.core import yaml_load as original_yaml_load
from more_itertools.more import side_effect


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

GSIM, IMT = 'gsim', 'imt'

# create a yaml dict that will mock yaml_load (from file)
with open(os.path.join(DATA_DIR, 'trellis_dist.yaml')) as fpt:
    yamldict = yaml.safe_load(fpt)


# @mock.patch('egsim.core import yaml_load', side_effect=yaml_load)
def test_compute_raises():
    with pytest.raises(YAMLError) as context:  # https://stackoverflow.com/a/3166985
        compute(os.path.join(DATA_DIR, 'trellis1'))
    with pytest.raises(YAMLError) as context:
        data = compute(os.path.join(DATA_DIR, 'trellis_malformed.yaml'))
    with pytest.raises(YAMLError) as context:
        data = compute(os.path.join(DATA_DIR, 'trellis_filenot_found.yaml'))


@mock.patch('egsim.core.yaml_load')
@pytest.mark.parametrize('trellis_type', ['d', 'ds'])
def test_trellis_dist(mock_yaml_load, trellis_type):
    '''test trellis distance and distance stdev'''
    mock_yaml_load.return_value = dict(yamldict, plot_type=trellis_type)
    data = compute(os.path.join(DATA_DIR, 'trellis_dist.yaml'))
    form = data[0]
    assert not form.errors and form.is_valid()
    # check output:
    result = data[1]
    input_ = form.clean()
    assert sorted(result.keys()) == ['figures', 'xlabel', 'xvalues']
    xvalues = result['xvalues']
    assert len(xvalues) == len(input_['distance']) + 1  # FIXME: should be len(distance)!!!
    figures = result['figures']
    assert len(figures) == len(input_['magnitude']) * len(input_['imt'])
    for fig in figures:
        yvalues = fig['yvalues']
        assert all(len(yval) == len(xvalues) for yval in yvalues.values())
        assert sorted(yvalues.keys()) == sorted(input_['gsim'])


@mock.patch('egsim.core.yaml_load')
@pytest.mark.parametrize('trellis_type', ['m', 'ms'])
def test_trellis_mag(mock_yaml_load, trellis_type):
    '''test trellis magnitude and magnitude stdev'''
    mock_yaml_load.return_value = dict(yamldict, plot_type=trellis_type)
    data = compute(os.path.join(DATA_DIR, 'trellis_dist.yaml'))
    form = data[0]
    assert not form.errors and form.is_valid()
    # check output:
    result = data[1]
    input_ = form.clean()
    assert sorted(result.keys()) == ['figures', 'xlabel', 'xvalues']
    xvalues = result['xvalues']
    assert len(xvalues) == len(input_['magnitude'])
    figures = result['figures']
    assert len(figures) == len(input_['distance']) * len(input_['imt'])
    for fig in figures:
        yvalues = fig['yvalues']
        assert all(len(yval) == len(xvalues) for yval in yvalues.values())
        assert sorted(yvalues.keys()) == sorted(input_['gsim'])


@mock.patch('egsim.core.yaml_load')
@pytest.mark.parametrize('trellis_type', ['s', 'ss'])
def test_trellis_spec(mock_yaml_load, trellis_type):
    '''test trellis magnitude-distance spectra and magnitude-distance stdev'''
    mock_yaml_load.return_value = dict(yamldict, plot_type=trellis_type)
    data = compute(os.path.join(DATA_DIR, 'trellis_dist.yaml'))
    form = data[0]
    assert not form.errors and form.is_valid()
    # check output:
    result = data[1]
    input_ = form.clean()
    assert sorted(result.keys()) == ['figures', 'xlabel', 'xvalues']
    xvalues = result['xvalues']
    assert len(xvalues) == len(default_periods_for_spectra())
    figures = result['figures']
    assert len(figures) == len(input_['distance']) * len(input_['magnitude'])
    for fig in figures:
        yvalues = fig['yvalues']
        assert all(len(yval) == len(xvalues) for yval in yvalues.values())
        assert sorted(yvalues.keys()) == sorted(input_['gsim'])


def test_error():
    params = {"gsim": ["AbrahamsonEtAl2014", "AbrahamsonEtAl2014NSHMPLower",
                       "AbrahamsonEtAl2014NSHMPMean", "AbrahamsonEtAl2014NSHMPUpper",
                       "AbrahamsonEtAl2014RegCHN", "AbrahamsonEtAl2014RegJPN",
                       "AbrahamsonEtAl2014RegTWN", "AkkarBommer2010SWISS01",
                       "AkkarBommer2010SWISS04", "AkkarBommer2010SWISS08",
                       "AkkarEtAl2013", "AkkarEtAlRepi2014"],
              "imt": ["PGA", "PGV"], "magnitude": "3:4", "distance": "10:12", "dip": "60",
              "aspect": "1.5", "rake": "0.0", "ztor": "0.0", "strike": "0.0", "msr": "WC1994",
              "initial_point": "0 0", "hypocentre_location": "0.5 0.5", "vs30": "760.0",
              "vs30_measured": True, "line_azimuth": "0.0", "plot_type": "ds"}
    form, result = compute(params)
    figures = result['figures']
    assert figures[1]['yvalues']['AkkarBommer2010SWISS01'] == []
