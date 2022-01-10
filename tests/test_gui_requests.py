"""
Tests GUI requests and functions

Created on 2 Jun 2018

@author: riccardo
"""
from io import StringIO

import yaml
import json
import pytest

from egsim.api.forms.model_from_region.model_from_region import ModelFromRegionForm
from egsim.api.forms.model_to_data.residuals import ResidualsForm
from egsim.api.forms.model_to_data.testing import TestingForm
from egsim.api.forms.model_to_model.trellis import TrellisForm

from egsim.gui.vuejs import form_to_json, get_components_properties
from egsim.api.forms.tools.describe import as_dict

GSIM, IMT = 'gsim', 'imt'


@pytest.mark.django_db
class Test:

    def test_get_component_properties(self):
        data = get_components_properties(debugging=False)
        # test it is json serializable:
        json.dumps(data)

    def test_to_vuejs(self):
        val = [form_to_json(_) for _ in (TrellisForm, ResidualsForm, TestingForm)]
        # test it is json serializable:
        data = json.dumps(val)

    def test_to_help(self):
        val = [as_dict(_) for _ in (TrellisForm, ResidualsForm, TestingForm)]
        # test it is json serializable:
        data = json.dumps(val)

    def test_get_gsim_from_region(self):
        form = ModelFromRegionForm({'lat': 50, 'lon': 7})
        assert form.is_valid()
        resp = form.response_data
        asd = 9
