'''
Tests forms functionalities

Created on 2 Jun 2018

@author: riccardo
'''
import json

import pytest
from openquake.hazardlib import imt

from egsim.api.forms import GsimImtForm
from egsim.api.forms.model_to_model.trellis import TrellisForm
# from egsim.api.core.utils import yaml_load, MOF
# from egsim.api.forms.fields import MeasureOfFitField
from django.core.exceptions import ValidationError

from egsim.gui.vuejs import to_help_dict

GSIM, IMT = 'gsim', 'imt'

@pytest.mark.django_db
def test_form_rendering_dict():
    a = list(to_help_dict(TrellisForm()))
    asd = 9

@pytest.mark.django_db
def test_gsimimt_form_invalid(areequal):  # areequal: fixture in conftest.py
    '''tests the gsimimt form invalid case. The form is the base class for all
    forms using imgt and gsim as input'''
    form = GsimImtForm()
    assert not form.is_valid()
    # https://docs.djangoproject.com/en/2.0/ref/forms/api/#django.forms.Form.is_bound:
    assert not form.is_bound
    # Note (from url link above):
    #  There is no way to change data in a Form instance.
    # Once a Form instance has been created, you should consider its data
    # immutable, whether it has data or not.
    err = form.errors.as_json()
    assert err == '{}'

    form = GsimImtForm({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb']})
    assert not form.is_valid()
    err = json.loads(form.errors.as_json())
    expected_err = {
        "imt": [
            {
                "message": "This field is required.",
                "code": "required"
            }
        ]
    }
    assert areequal(err, expected_err)

    form = GsimImtForm({GSIM: ['abcde', 'BindiEtAl2014Rjb']})
    assert not form.is_valid()
    err = json.loads(form.errors.as_json())
    expected_err = {
        "gsim": [
            {
                "message": ("Select a valid choice. abcde is not one of the "
                            "available choices."),
                "code": "invalid_choice"
            }
        ],
        "imt": [
            {
                "message": "This field is required.",
                "code": "required"
            }
        ]
    }
    assert areequal(err, expected_err)

    form = GsimImtForm({IMT: ['abcde', 'BindiEtAl2014Rjb']})
    assert not form.is_valid()
    err = json.loads(form.errors.as_json())
    expected_err = {
        'gsim': [
            {
                'message': 'This field is required.',
                'code': 'required'
            }
        ],
        'imt': [
            {
                'message': ('Select a valid choice. abcde is not one of the '
                            'available choices.'),
                'code': 'invalid_choice'
            }
        ]
    }
    assert areequal(err, expected_err)

    form = GsimImtForm({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                        IMT: ['SA', 'MMI']})
    assert not form.is_valid()
    err = form.errors.as_json()

    # ------------------------------------------------------------------------
    # UNCOMMENT IF PROVIDING UNKNOWN PARAMETER RAISES (FOR NOW IT DOES NOT):
    # ------------------------------------------------------------------------
#     form = GsimImtForm({'unknown_param': 5,
#                         GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
#                      IMT: ['SA(0.1)', 'SA(0.2)', 'PGA', 'PGV']})
#     assert not form.is_valid()
#     err = form.errors.as_json()

    data = {
        GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
        IMT: ['SA', 'PGA', 'PGV']
    }
    form = GsimImtForm(data)
    assert not form.is_valid()
    expected_dict = {
        'imt': [
            {
                'message': 'SA must be specified with period(s)',
                'code': 'sa_without_period'
            }
        ]
    }
    assert areequal(json.loads(form.errors.as_json()), expected_dict)


@pytest.mark.django_db
@pytest.mark.parametrize('data',
                         [({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                            IMT: ['SA(0.1)', 'SA(0.2)', 'PGA', 'PGV']}),
                          ({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                            IMT: ['SA', 'PGA', 'PGV'],
                            'sa_period': '0.1:0.1:0.2'}),
                          ({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                            IMT: ['PGA', 'PGV'],
                            'sa_period': '0.1:0.1:0.2'})])
def test_gsimimt_form_valid(data,
                            areequal):  # areequal: fixture in conftest.py
    form = GsimImtForm(data)
    assert form.is_valid()
    dic = form.cleaned_data
    # This does not work:
    # assert dic == data
    # because we processed the imts
    assert areequal(dic['gsim'], data['gsim'])
    imts = dic['imt']
    assert 'PGA' in imts
    assert 'PGV' in imts
    # to test SA's it's complicated, they should be 'SA(0.1)', 'SA(0.2)'
    # IN PRINCIPLE but due to rounding errors they might be slighlty different.
    # So do not test for string equality but create imts and test for
    # 'period' equality:
    imts = sorted([imt.from_string(i) for i in imts if i not in
                   ('PGA', 'PGV')], key=lambda imt: imt.period)
    assert imts[0].period == 0.1
    assert imts[1].period == 0.2


@pytest.mark.django_db
@pytest.mark.parametrize('data',
                         [({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                            IMT: ['SA(r)', 'SA(0.2)', 'PGA', 'PGV']}),
                          ({GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                            IMT: ['SA', 'PGA', 'PGV'],
                            'sa_period': 'r:0.1:0.2'})])
def test_gsimimt_form_invalid_periods(data,
                                      # pytest fixtures:
                                      areequal):
    form = GsimImtForm(data)
    assert not form.is_valid()
    err_json = json.loads(form.errors.as_json())
    assert list(err_json.keys()) == ['imt']
    assert len(err_json['imt']) == 1
    assert err_json['imt'][0]['code'] == 'invalid_sa_period'


@pytest.mark.django_db
@pytest.mark.parametrize('data',
                         [({GSIM: ['AllenEtAl2012'],  # not defined for SA
                            IMT: ['SA(r)', 'SA(0.2)', 'PGA', 'PGV']}),
                          ({GSIM: ['AllenEtAl2012'],  # not defined for SA
                            IMT: ['SA', 'PGA', 'PGV'],
                            'sa_period': 'r:0.1:0.2'})])
def test_gsimimt_form_notdefinedfor_skip_invalid_periods(data,
                                                         # pytest fixtures:
                                                         areequal):
    '''tests that mismatching gsim <-> imt has the priority over bad
    SA periods'''
    form = GsimImtForm(data)
    assert not form.is_valid()
    expected_err = {
        'gsim': [
            {
                'message': '1 gsim(s) not defined for all supplied imt(s)',
                'code': 'invalid'
            }
        ],
        'imt': [
            {
                'message': '3 imt(s) not defined for all supplied gsim(s)',
                'code': 'invalid'
            }
        ]
    }
    assert areequal(json.loads(form.errors.as_json()), expected_err)


@pytest.mark.django_db
def test_arrayfields_all_valid_input_types():
    '''Tests some valid inputs in the egsim Fields accepting array of values
    (MultipleChoiceWildcardField and NArrayField) using the trellis form
    because it's the most heterogeneous. What we want to check is:
    1. a MultipleChoiceWildcardField can be input as string S and will be
        returned as the 1-element list [S] (param GSIM)
    2. NArrayField can be input as string with space- or comma-separated
        string chunks (or matlab range notation), but also:
        2a. As python number (param magnitude)
        2b. As string parsable to float (param distance)
        2c. As list of any of the above types (param vs30)
    3. A MultipleChoiceWildcardField expands wildcards not only if
        the input is a string, but also, if the input is a list of strings,
        for all list sub-elements (param imt)
    '''
    data = {
        GSIM: 'BindiEtAl2011',
        IMT: ['PG[AV]'],  # ['SA(0.1)', 'PGA', 'PGV'],
        'magnitude': 0.5,
        'distance': '0.1',
        'dip': 60,
        'vs30': [60, '76'],
        'plot_type': 'm',
        'aspect': 1
    }
    form = TrellisForm(data)
    assert form.is_valid()
    assert form.cleaned_data[GSIM] == ['BindiEtAl2011']  # testing 1)
    assert form.cleaned_data['magnitude'] == 0.5  # testing 2a)
    assert form.cleaned_data['distance'] == 0.1  # testing 2b)
    assert form.cleaned_data['vs30'] == [60, 76]  # testing 2c)
    assert sorted(form.cleaned_data['imt']) == ['PGA', 'PGV']  # testing 3)


@pytest.mark.django_db
def test_multuplechoicefield_simplestring():
    '''Tests that a django MultipleChoiceField does NOT accept a string input
    (whereas an egsim MultipleChoiceWildcardField does, and converts the string
    to a 1-element list)
    '''
    mof = MeasureOfFitField()
    mof.clean([MOF.RES])
    with pytest.raises(ValidationError):
        mof.clean(MOF.RES)


@pytest.mark.django_db
def test_trellisform_invalid(areequal):
    '''Tests trellis form invalid.
    :param comparator: pytest fixture defined in conftest.py, it is used to
    compare objects with optional error tolerance for numeric array, and other
    utilities (e.g. two lists with same items in different orders are equal)
    '''
    data = {GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
            IMT: ['SA', 'PGA', 'PGV']}

    form = TrellisForm(data)
    assert not form.is_valid()
    err = form.errors.as_json()
    expected_json = {
        'imt': [
            {
                'message': 'SA must be specified with period(s)',
                'code': 'sa_without_period'
            }
        ],
        'plot_type': [
            {
                'message': 'This field is required.',
                'code': 'required'
            }
        ],
        'magnitude': [
            {
                'message': 'This field is required.',
                'code': 'required'
            }
        ],
        'distance': [
            {
                'message': 'This field is required.',
                'code': 'required'
            }
        ],
        'aspect': [
            {
                'message': 'This field is required.',
                'code': 'required'
            }
        ],
        'dip': [
            {
                'message': 'This field is required.',
                'code': 'required'
            }
        ]
    }
    assert areequal(json.loads(err), expected_json)

    # test invalid by supplying some parameters:
    data = {GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
            IMT: ['SA(0.1)', 'PGA', 'PGV']}
    form = TrellisForm(dict(data, magnitude='0:1:5', distance=6, dip=56,
                            aspect='ert'))
    assert not form.is_valid()

    err = form.errors.as_json()
    expected_json = {
        "aspect": [
            {
                "message": "Enter a number.",
                "code": "invalid"
            }
        ],
        "plot_type": [
            {
                "message": "This field is required.",
                "code": "required"
            }
        ]
    }
    assert areequal(json.loads(err), expected_json)


@pytest.mark.django_db
@pytest.mark.parametrize('data, expected_mag_yaml, expected_mag_json',
                         [(
                             {
                                 GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                                 IMT: ['SA(0.1)', 'SA(0.2)', 'PGA', 'PGV'],
                                 'aspect': 1.2,
                                 'dip': 5, 'magnitude': '1:1:5',
                                 'distance': [1, 2, 3, 4, 5],
                                 'z1pt0': 34.5,
                                 'initial_point': '0 1',
                                 'plot_type': 'm'
                              },
                             " '1:1:5'",
                             '"1:1:5"'
                           ),
                          (
                              {
                                  GSIM: ['BindiEtAl2011', 'BindiEtAl2014Rjb'],
                                  IMT: ['SA(0.1)', 'SA(0.2)', 'PGA', 'PGV'],
                                  'aspect': 1.2,
                                  'dip': 5, 'magnitude': [1, 2, 3, 4, 5],
                                  'distance': [1, 2, 3, 4, 5],
                                  'z1pt0': 34.5,
                                  'initial_point': '0 1',
                                  'plot_type': 'm'}, """
  - 1
  - 2
  - 3
  - 4
  - 5""", """[
        1,
        2,
        3,
        4,
        5
    ]""")])
def test_trellisform_load_dump(data, expected_mag_yaml, expected_mag_json,
                               # pytest fixtures:
                               areequal):
    '''test that form serialization works for ndarray given as range and
    arrays (in the first case preserves the string with colons, and that a
    Form taking the serialized yaml has the same clean() method as the original
    form's clean method'''
    form = TrellisForm(data)
    assert form.is_valid()

    with pytest.raises(ValueError):  # @UndefinedVariable
        form.dump(syntax='whatever')

    cleaned_data = form.cleaned_data
    yaml_ = form.dump(syntax='yaml')
    json_ = form.dump(syntax='json')

    # pass the yaml and json to validate and see that we obtain the same
    # dict(s):
    form_from_yaml = TrellisForm(data=yaml_load(yaml_))
    assert form_from_yaml.is_valid()
    assert areequal(cleaned_data, form_from_yaml.cleaned_data)

    form_from_json = TrellisForm(data=yaml_load(json_))
    assert form_from_json.is_valid()
    assert areequal(cleaned_data, form_from_json.cleaned_data)

    expected_json_ = """{
    "aspect": 1.2,
    "dip": 5,
    "distance": [
        1,
        2,
        3,
        4,
        5
    ],
    "gsim": [
        "BindiEtAl2011",
        "BindiEtAl2014Rjb"
    ],
    "imt": [
        "SA(0.1)",
        "SA(0.2)",
        "PGA",
        "PGV"
    ],
    "initial_point": "0 1",
    "magnitude": %s,
    "plot_type": "m",
    "z1pt0": 34.5
}""" % expected_mag_json

    assert expected_json_ == json_

    expected_yaml_ = """# Ground Shaking Intensity Model(s)
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
dip: 5

# Magnitude(s)
magnitude:%s

# Distance(s)
distance:
  - 1
  - 2
  - 3
  - 4
  - 5

# Depth to 1 km/s VS layer (m) (Calculated from the VS30 if not given)
z1pt0: 34.5

# Location on Earth (Longitude Latitude)
initial_point: 0 1

# Plot type
plot_type: m

""" % expected_mag_yaml

    assert expected_yaml_ == yaml_
