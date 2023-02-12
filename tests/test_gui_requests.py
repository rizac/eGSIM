"""
Tests GUI requests and functions

Created on 2 Jun 2018

@author: riccardo
"""
import json
import pytest

from egsim.api.forms import GsimFromRegionForm, _get_regionalizations
from egsim.api.forms.flatfile.residuals import ResidualsForm
from egsim.api.forms.flatfile.testing import TestingForm
from egsim.api.forms.trellis import TrellisForm

# from egsim.api.forms.tools.describe import as_dict
# from egsim.gui.frontend import get_context, form_to_json
from egsim.app.templates.apidoc import as_dict
from egsim.app.templates.egsim import get_init_json_data, form_to_json

GSIM, IMT = 'gsim', 'imt'

@pytest.mark.django_db
class Test:

    def test_get_component_properties(self):
        data = get_init_json_data(debug=False)
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
        # query each regionalization singularly and check that we get the same models:
        resp = set(form.response_data)
        regs = [_[0] for _ in _get_regionalizations()]
        resp2 = []
        for reg in regs:
            resp_ = set(GsimFromRegionForm({'lat': 50, 'lon': 7, 'shsr': reg}).response_data)
            assert sorted(resp_ & resp) == sorted(resp_)
            resp2.extend(resp_)
        assert sorted(resp) == sorted(resp2)
