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

from egsim.api.forms.flatfile import FlatfileMetadataInfoForm, FlatfileValidationForm
from egsim.api.forms.residuals import ResidualsForm
from egsim.api.forms.scenarios import PredictionsForm
from egsim.app.forms import FlatfilePlotForm

# from egsim.app.views import _IMG_FORMATS
# from egsim.app.templates.apidoc import as_dict
from egsim.app.views import URLS
from django.test.client import Client

GSIM, IMT = 'gsim', 'imt'

@pytest.mark.django_db
class Test:

    def test_to_help(self):
        def_ = { GSIM: ['CauzziEtAl2014'], IMT: ['PGA']}
        f_ = {'flatfile': 'esm_2018'}

        for form, compact in product(
                [PredictionsForm(def_),
                 ResidualsForm(def_ | f_),
                 FlatfileMetadataInfoForm(def_),
                 FlatfileValidationForm(f_),
                 FlatfilePlotForm(f_ | {'x': 'mag'})],
                [True, False]):
            val = form.asdict(compact)
            # test it is json serializable:
            data = json.dumps(val)

    def test_html_pages(self,  # pytest fixtures:
                        client):
        page_urls = [getattr(URLS, _) for _ in dir(URLS) if _.endswith('_PAGE')]
        assert len(page_urls)  # in case we rename the attrs sometime
        for url in page_urls:

            # external link, just check the link ios n ot broken:
            if url.startswith('http://') or url.startswith('https://'):
                import urllib.request
                with urllib.request.urlopen(url) as response:
                    assert response.code == 200
                continue

            # just the URL without leading slash returns 404 (FIXME WHY?)
            response = client.get(f"{url}" , follow=True)
            assert response.status_code == 404

            # leading
            response = client.get(f"/{url}", follow=True)
            assert response.status_code == 200

            # trailing slash al;so work (see urls.py)
            response = client.get(f"/{url}/", follow=True)
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

    def tst_main_page_init_data_and_invalid_browser_message(self, settings):
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
