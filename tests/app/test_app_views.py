"""
Tests GUI requests and functions

Created on 2 Jun 2018

@author: riccardo
"""
from django.core.files.uploadedfile import SimpleUploadedFile
from io import BytesIO

import yaml

from itertools import product

import json
import pytest

from egsim.api.forms.flatfile.residuals import ResidualsForm
from egsim.api.forms.predictions import PredictionsForm


from egsim.app.views import _IMG_FORMATS
from egsim.app.templates.apidoc import as_dict
from egsim.app.templates.egsim import get_init_json_data, form_to_json, URLS, TAB
from django.test.client import Client

GSIM, IMT = 'gsim', 'imt'

@pytest.mark.django_db
class Test:

    def test_get_component_properties(self):
        data = get_init_json_data(debug=False)
        # test it is json serializable:
        json.dumps(data)

    def test_to_vuejs(self):
        val = [form_to_json(_) for _ in (PredictionsForm, ResidualsForm)]
        # test it is json serializable:
        data = json.dumps(val)

    def test_to_help(self):
        val = [as_dict(_) for _ in (PredictionsForm, ResidualsForm)]
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

    def test_flatfile_inspection(self,  # pytest fixtures:
                                 testdata):
            url  = URLS.FLATFILE_INSPECTION
            ff = SimpleUploadedFile('flatfile',
                                    testdata.read('Turkey_20230206_flatfile_geometric_mean.csv'))
            data = {'flatfile': ff}
            client = Client()  # do not use the fixture client as we want
            # to disable CSRF Token check
            response = client.post("/" + url, data=data)
            assert response.status_code == 200

    def test_flatfile_plot(self,  # pytest fixtures:
                           testdata):
            url = URLS.FLATFILE_PLOT
            ff_bytes = testdata.read('Turkey_20230206_flatfile_geometric_mean.csv')
            ff = SimpleUploadedFile('flatfile',ff_bytes)
            data = {'flatfile': ff}
            client = Client()  # do not use the fixture client as we want
            # to disable CSRF Token check
            response = client.post("/" + url, data=data)
            assert response.status_code == 400  # no x and y
            msg = response.json()['error']['message']
            assert "x" in msg and 'y' in msg

            for data in [
                {'x': 'magnitude'},
                {'x': 'PGA'},
                {'x': 'magnitude', 'y': 'PGA'},
                {'y': 'magnitude', 'x': 'PGA'}
            ]:
                ff = SimpleUploadedFile('flatfile', ff_bytes)
                data['flatfile'] = ff  # noqa
                client = Client()  # do not use the fixture client as we want
                # to disable CSRF Token check
                response = client.post("/" + url, data=data)
                assert response.status_code == 200

    def test_main_page_init_data_and_invalid_browser_message(self, settings):
        data = [{'browser': {'name': bn, 'version': v}, 'selectedMenu': m }
                for bn, v, m in product(['chrome', 'firefox', 'safari'],
                                        [1, 100000], [_.name for _ in TAB])]
        data += [{'browser': {'name': 'opera', 'version': 100000}}]
        for d in data:
            # test with settings.DEBUG = True only for opera
            settings.DEBUG = d['browser']['name'] == 'opera'
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

    def test_download_request(self, #pytest fixture:
                               testdata, areequal):
        for service in ['trellis', 'residuals', 'testing']:
            with open(testdata.path(f'request_{service}.yaml')) as _:
                data = yaml.safe_load(_)
            if service == 'residuals':
                data['plot'] = 'res'
            client = Client()  # do not use the fixture client as we want
            for filename in ['request.json', 'request.yaml', 'request.querystring']:
                # to disable CSRF Token check
                response = client.post(f"/{URLS.DOWNLOAD_REQUEST}/{service}/{filename}",
                                       json.dumps(data),
                                       content_type="application/json")
                assert response.status_code == 200
                if service == 'json':
                    assert areequal(data, json.loads(response.content))
                elif service == '.yaml':
                    assert areequal(data, yaml.safe_load(BytesIO(response.content)))
                else:
                    assert True

    def test_download_response_csv_formats(self,  # pytest fixture:
                                           testdata, areequal):
        for service in ['trellis', 'residuals', 'testing']:
            with open(testdata.path(f'request_{service}.yaml')) as _:
                data = yaml.safe_load(_)
            if service == 'residuals':
                data['plot'] = 'res'
            response_data, _ = {
                'trellis': PredictionsForm,
                'residuals': ResidualsForm,
                # 'testing': TestingForm
            }[service](data).response_data
            client = Client()  # do not use the fixture client as we want
            # Note below: json is not supported because from the browser we simply
            # serve the already available response_data
            for filename in ['response.csv', 'response.csv_eu']:
                # to disable CSRF Token check
                response = client.post(f"/{URLS.DOWNLOAD_RESPONSE}/{service}/{filename}",
                                       json.dumps(response_data),
                                       content_type="application/json")
                assert response.status_code == 200

    def test_download_response_img_formats(self,  # pytest fixture:
                                           testdata, areequal):
        for service in ['trellis']:  # , 'residuals', 'testing']:
            # for the moment, just provide a global data object regardless of the
            # service:
            data = [
                {
                    'x': [1, 2],
                    'y': [1, 2],
                    'type': 'scatter',
                    'name': '(1,1)'
                },
                {
                    'x': [1, 2],
                    'y': [1, 2],
                    'type': 'bar',
                    'name': '(1,2)',
                    'xaxis': 'x2',
                    'yaxis': 'y2'
                },
                {
                    'x': [1, 2],
                    'y': [1, 2],
                    # 'type': 'line',
                    'name': '(1,2)',
                    'xaxis': 'x3',
                    'yaxis': 'y3'
                },
                {
                    'x': [1, 2],
                    'y': [1, 2],
                    'type': 'histogram',
                    'name': '(1,2)',
                    'xaxis': 'x4',
                    'yaxis': 'y4'
                }
            ]
            layout = {
                'title': 'Multiple Custom Sized Subplots',
                'xaxis': {
                    'domain': [0, 0.45],
                    'anchor': 'y1'
                },
                'yaxis': {
                    'domain': [0.5, 1],
                    'anchor': 'x1'
                },
                'xaxis2': {
                    'domain': [0.55, 1],
                    'anchor': 'y2'
                },
                'yaxis2': {
                    'domain': [0.8, 1],
                    'anchor': 'x2'
                },
                'xaxis3': {
                    'domain': [0.55, 1],
                    'anchor': 'y3'
                },
                'yaxis3': {
                    'domain': [0.5, 0.75],
                    'anchor': 'x3'
                },
                'xaxis4': {
                    'domain': [0, 1],
                    'anchor': 'y4'
                },
                'yaxis4': {
                    'domain': [0, 0.45],
                    'anchor': 'x4'
                }
            }
            client = Client()  # do not use the fixture client as we want
            # Note below: json is not supported because from the browser we simply
            # serve the already available response_data
            for filename in ['response.' + _ for _ in _IMG_FORMATS.keys()]:
                # to disable CSRF Token check
                response = client.post(f"/{URLS.DOWNLOAD_RESPONSE}/{service}/{filename}",
                                       json.dumps({'data': data, 'layout': layout,
                                                   'width': 100, 'height': 100}),
                                       content_type="application/json")
                assert response.status_code == 200
