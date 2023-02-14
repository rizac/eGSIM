"""
Tests GUI requests and functions

Created on 2 Jun 2018

@author: riccardo
"""
from unittest.mock import patch

from itertools import product

import json
import pytest

# from egsim.api.forms import GsimFromRegionForm, _get_regionalizations
from egsim.api.forms.flatfile.residuals import ResidualsForm
from egsim.api.forms.flatfile.testing import TestingForm
from egsim.api.forms.trellis import TrellisForm

# from egsim.api.forms.tools.describe import as_dict
# from egsim.gui.frontend import get_context, form_to_json
from egsim.app.templates.apidoc import as_dict
from egsim.app.templates.egsim import get_init_json_data, form_to_json, URLS, TAB, \
    _get_gsim_for_init_data
from django.test.client import Client
# from egsim.app.urls import urlpatterns

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

    def test_views(self,  # pytest fixtures:
                   client):
        for url in [URLS.IMPRINT, URLS.HOME_NO_MENU, URLS.REF_AND_LICENSE,  # URLS.API,
                    URLS.GET_GSIMS_FROM_REGION,  # URLS.FLATFILE_INSPECTION, URLS.FLATFILE_PLOT
                    URLS.FLATFILE_REQUIRED_COLUMNS] + \
                   [_.name for _ in TAB]:
            response = client.get("/" + url , follow=True)
            assert response.status_code == 200

    def test_main_page_init_data_and_invalid_browser_message(self):
        # first test the method for getting all gsim in init data (uses db prefetch):
        _models = list(_get_gsim_for_init_data())
        # then mock it (since it is time consuming) when testing several possible
        # combination of _get_init_data:
        # with patch('egsim.app.templates.egsim._get_gsim_for_init_data',
        #            side_effect=lambda *a, **v: _models) as _:
        data = [{'browser': {'name': bn, 'version': v}, 'selectedMenu': m }
                for bn, v, m in product(['chrome', 'firefox', 'safari', 'opera'],
                                        [1, 100000], [_.name for _ in TAB])]
        for d in data:
            client = Client()  # do not use the fixture client as we want
            # to disable CSRF Token check
            response = client.post('/' + URLS.MAIN_PAGE_INIT_DATA, json.dumps(d),
                                   content_type="application/json")
            assert response.status_code == 200
            content = json.loads(response.content)
            if d['browser']['version'] == 1 or d['browser']['name'] == 'opera':
                assert content['invalid_browser_message']
            else:
                assert not content['invalid_browser_message']