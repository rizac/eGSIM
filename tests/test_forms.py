'''
Created on 2 Jun 2018

@author: riccardo
'''
import numpy as np

import pytest

from egsim.forms.forms import TrellisForm, GsimImtForm
from openquake.hazardlib import imt
import json


GSIM, IMT = 'gsim', 'imt'


def test_gsimimtForm_invalid():
    form = GsimImtForm()
    assert not form.is_valid()
    # https://docs.djangoproject.com/en/2.0/ref/forms/api/#django.forms.Form.is_bound:
    assert not form.is_bound
    # Note (from url link above):
    #  There is no way to change data in a Form instance.
    # Once a Form instance has been created, you should consider its data immutable,
    # whether it has data or not.
    err = form.errors.as_json()
    assert err == '{}'

    form = GsimImtForm({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb']})
    assert not form.is_valid()
    err = form.errors.as_json()
    assert err == '{"imt": [{"message": "This field is required.", "code": "required"}]}'

    form = GsimImtForm({GSIM: ['abcde', 'BindiEtAl2014Rjb']})
    assert not form.is_valid()
    err = form.errors.as_json()
    assert err == ('{"gsim": [{"message": "Select a valid choice. abcde is not one of '
                   'the available choices.", '
                   '"code": "invalid_choice"}], "imt": [{"message": "This field is required.",'
                   ' "code": "required"}]}')

    form = GsimImtForm({IMT: ['abcde', 'BindiEtAl2014Rjb']})
    assert not form.is_valid()
    err = form.errors.as_json()
    assert err == ('{"gsim": [{"message": "This field is required.", "code": "required"}], '
                   '"imt": [{"message": "Select a valid choice. abcde is not one of the '
                   'available choices.", "code": "invalid_choice"}]}')

    form = GsimImtForm({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'], IMT: ['SA', 'MMI']})
    assert not form.is_valid()
    err = form.errors.as_json()

    # ----------------------------------------------------------------------------
    # UNCOMMENT IF PROVIDING UNKNOWN PARAMETER RAISES (FOR THE MOMENT IT DOES NOT):
    # ----------------------------------------------------------------------------
#     form = GsimImtForm({'unknown_param': 5, GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
#                      IMT: ['SA(0.1)', 'SA(0.2)', 'PGA', 'PGV']})
#     assert not form.is_valid()
#     err = form.errors.as_json()

    data = {GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'], IMT: ['SA', 'PGA', 'PGV']}
    form = GsimImtForm(data)
    assert not form.is_valid()
    err = form.errors.as_json()
    expected_json = \
        ('{"imt": '
         '[{"message": "intensity measure type \'SA\' must be specified with period(s)",'
         ' "code": "sa_without_period"}]}')
    assert err == expected_json


@pytest.mark.parametrize('data', [({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                                    IMT: ['SA(0.1)', 'SA(0.2)', 'PGA', 'PGV']}),
                                  ({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                                    IMT: ['SA', 'PGA', 'PGV'],
                                    'sa_periods': '0.1:0.1:0.2'})])
def test_gsimimtForm_valid(data):
    form = GsimImtForm(data)
    assert form.is_valid()
    dic = form.cleaned_data
    # This does not work:
    # assert dic == data
    # because we processed the imts
    assert dic['gsim'] == data['gsim']
    imts = dic['imt']
    assert 'PGA' in imts
    assert 'PGV' in imts
    # to test SA's it's complicated, they should be 'SA(0.1)', 'SA(0.2)' IN PRINCIPLE
    # but due to rounding errors they might be slighlty different. So do not test for
    # string equality but create imts and test for 'period' equality:
    imts = sorted([imt.from_string(i) for i in imts if i not in ('PGA', 'PGV')],
                  key=lambda imt: imt.period)
    assert imts[0].period == 0.1
    assert imts[1].period == 0.2


def test_trellisform_invalid(comparator):
    '''Tests trellis form invalid.
    :param comparator: pytest fixture defined in conftest.py, it is used to compare
    objects with optional error tolerance for numeric array, and other utilities (e.g.
    two lists with same items in different orders are equal)
    '''
    data = {GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'], IMT: ['SA', 'PGA', 'PGV']}

    form = TrellisForm(data)
    assert not form.is_valid()
    err = form.errors.as_json()
    expected_json = \
        ('{"imt": [{"message": "intensity measure type \'SA\' must be '
         'specified with period(s)", "code": "sa_without_period"}], '
         '"plot_type": [{"message": "This field is required.", "code": "required"}], '
         '"magnitude": [{"message": "This field is required.", "code": "required"}], '
         '"distance": [{"message": "This field is required.", "code": "required"}], '
         '"dip": [{"message": "This field is required.", "code": "required"}], '
         '"aspect": [{"message": "This field is required.", "code": "required"}]}')
    assert comparator.equal(json.loads(err), json.loads(expected_json))

    # test invalid by supplying some parameters:
    data = {GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'], IMT: ['SA(0.1)', 'PGA', 'PGV']}
    form = TrellisForm(dict(data, magnitude='0:1:5', distance=6, dip=56, aspect='ert'))
    assert not form.is_valid()

    err = form.errors.as_json()
    assert comparator.equal(json.loads(err),
                            json.loads('{"aspect": [{"message": "Enter a number.", '
                                       '"code": "invalid"}], '
                                       '"plot_type": [{"message": "This field is required.", '
                                       '"code": "required"}]}'))


@pytest.mark.parametrize('data, expected_yaml, expected_json',
                         [({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                            IMT: ['SA(0.1)', 'SA(0.2)', 'PGA', 'PGV'], 'aspect': 1.2,
                            'dip': 5, 'magnitude': '1:1:5', 'distance': [1, 2, 3, 4, 5],
                            'plot_type': 'm'}, " '1:1:5'", '"1:1:5"'),
                          ({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                            IMT: ['SA(0.1)', 'SA(0.2)', 'PGA', 'PGV'], 'aspect': 1.2,
                            'dip': 5, 'magnitude': [1, 2, 3, 4, 5], 'distance': [1, 2, 3, 4, 5],
                            'plot_type': 'm'}, """
  - 1.0
  - 2.0
  - 3.0
  - 4.0
  - 5.0""", """[
    1.0,
    2.0,
    3.0,
    4.0,
    5.0
  ]""")])
def test_trellisform_load_dump(data, expected_yaml, expected_json):
    '''test that form serialization works for ndarray given as range and arrays (in the
    first case preserves the string with colons, and that a Form taking the serialized
    yaml has the same clean() method as the original form's clean method'''
    form = TrellisForm(data)
    assert form.is_valid()
    cleaned_data = form.cleaned_data
    yaml_ = form.dump(syntax='yaml')
    json_ = form.dump(syntax='json')

    # pass the yaml and json to validate and see that we obtain the same dict(s):
    form_from_yaml = TrellisForm.load(yaml_)
    assert form_from_yaml.is_valid()
    assert cleaned_data == form_from_yaml.cleaned_data

    form_from_json = TrellisForm.load(json_)
    assert form_from_json.is_valid()
    assert cleaned_data == form_from_json.cleaned_data

    with pytest.raises(ValueError):
        TrellisForm(data).dump(syntax='whatever')

    assert json_ == """{
  "aspect": 1.2,
  "backarc": false,
  "dip": 5.0,
  "distance": [
    1.0,
    2.0,
    3.0,
    4.0,
    5.0
  ],
  "gsim": [
    "BindiEtAl2011",
    "BindiEtAl2014Rjb"
  ],
  "hypocentre_location": [
    0.5,
    0.5
  ],
  "imt": [
    "SA(0.1)",
    "SA(0.2)",
    "PGA",
    "PGV"
  ],
  "initial_point": [
    0.0,
    0.0
  ],
  "line_azimuth": 0.0,
  "magnitude": %s,
  "magnitude_scalerel": "WC1994",
  "plot_type": "m",
  "rake": 0.0,
  "strike": 0.0,
  "vs30": 760.0,
  "vs30_measured": true,
  "ztor": 0.0
}""" % expected_json

    assert yaml_ == """# Ground Shaking Intensity Model(s)
gsim:
  - BindiEtAl2011
  - BindiEtAl2014Rjb

# Intensity Measure Type(s)
imt:
  - SA(0.1)
  - SA(0.2)
  - PGA
  - PGV

# Rupture Length / Width
aspect: 1.2

# Dip
dip: 5.0

# Magnitude(s)
magnitude:%s

# Distance(s)
distance:
  - 1.0
  - 2.0
  - 3.0
  - 4.0
  - 5.0

# Plot type
plot_type: m

# Rake
rake: 0.0

# Top of Rupture Depth (km)
ztor: 0.0

# Strike
strike: 0.0

# Magnitude Scaling Relation
magnitude_scalerel: WC1994

# Location on Earth (Longitude Latitude)
initial_point:
  - 0.0
  - 0.0

# Location of Hypocentre (Along-strike fraction, Down-dip fraction)
hypocentre_location:
  - 0.5
  - 0.5

# VS30 (m/s)
vs30: 760.0

# Is VS30 measured? (Otherwise is inferred)
vs30_measured: true

# Azimuth of Comparison Line
line_azimuth: 0.0

# Backarc Path
backarc: false

""" % expected_yaml
