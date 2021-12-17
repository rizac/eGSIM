"""
Tests GUI requests and functions

Created on 2 Jun 2018

@author: riccardo
"""
from io import StringIO

import yaml
import json
import pytest

from egsim.api.forms.model_to_model.trellis import TrellisForm

from egsim.gui.guiutils import to_help_dict, to_request_data

GSIM, IMT = 'gsim', 'imt'

@pytest.mark.django_db
class Test:

    def test_form_rendering_dict(self):
        to_help_dict(TrellisForm())
        # FIXME: deeper testing?

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
    def test_trellisform_load_dump(self, data, expected_mag_yaml, expected_mag_json,
                                   # pytest fixtures:
                                   areequal):
        """test that form serialization works for ndarray given as range and
        arrays (in the first case preserves the string with colons, and that a
        Form taking the serialized yaml has the same clean() method as the original
        form's clean method"""
        form = TrellisForm(data)
        assert form.is_valid()

        with pytest.raises(ValueError):
            to_request_data(form, syntax='whatever')

        cleaned_data = form.cleaned_data
        yaml_ = to_request_data(form, syntax='yaml')
        json_ = to_request_data(form, syntax='json')

        yaml_str = yaml_.getvalue()
        json_str = json_.getvalue()
        yaml_.seek(0)
        yaml_dict = yaml.safe_load(yaml_)
        json_.seek(0)
        json_dict = yaml.safe_load(json_)

        # pass the yaml and json to validate and see that we obtain the same
        # dict(s): note: pass a COPY OF THOSE DICTS!
        form_from_yaml = TrellisForm(data=dict(yaml_dict))
        assert form_from_yaml.is_valid()
        assert areequal(cleaned_data, form_from_yaml.cleaned_data)

        form_from_json = TrellisForm(data=dict(json_dict))
        assert form_from_json.is_valid()
        assert areequal(cleaned_data, form_from_json.cleaned_data)

        json_str_expected = """{
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
        "location": "0 1",
        "magnitude": %s,
        "plottype": "m",
        "z1pt0": 34.5
    }""" % expected_mag_json

        json_dict_expected = json.loads(json_str_expected)
        assert areequal(json_dict_expected, json_dict)

        yaml_str_expected = """# Ground Shaking Intensity Model(s)
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
    location: 0 1
    
    # Plot type
    plottype: m
    
    """ % expected_mag_yaml

        for line in yaml_str.splitlines():
            if line.startswith('#'):
                assert line in yaml_str

        yaml_dict_expected = yaml.safe_load(StringIO(yaml_str_expected))
        assert areequal(yaml_dict_expected, yaml_dict)

@pytest.mark.django_db
def test_get_widgetdata():
    from egsim.gui.guiutils import get_widgetdata
    d = [get_widgetdata(f) for f in TrellisForm.declared_fields.values()]
    asd = 9