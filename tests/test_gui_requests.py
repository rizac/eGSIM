"""
Tests GUI requests and functions

Created on 2 Jun 2018

@author: riccardo
"""
import json
import pytest

from egsim.api.forms import GsimFromRegionForm
from egsim.api.forms.flatfile.residuals import ResidualsForm
from egsim.api.forms.flatfile.testing import TestingForm
from egsim.api.forms.trellis import TrellisForm

from egsim.api.forms.tools.describe import as_dict
from egsim.gui.frontend import get_context, form_to_json

GSIM, IMT = 'gsim', 'imt'

@pytest.mark.django_db
class Test:

    def test_get_component_properties(self):
        data = get_context(debug=False)
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

    def test_get_gsim_from_region(self, areequal):
        form = GsimFromRegionForm({'lat': 50, 'lon': 7})
        assert form.is_valid()
        resp = form.response_data
        for res, reg in resp.items():
            dict_test = {k: v for k, v in resp.items() if v == reg}
            resp_ = GsimFromRegionForm({'lat': 50, 'lon': 7, 'reg': reg}).response_data
            assert resp_ == dict_test
        asd = 9
