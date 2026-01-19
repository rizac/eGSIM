"""
Tests for app requests and functions
"""
from urllib.error import URLError

from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
import os
import pandas as pd
from os.path import dirname, join, abspath, isfile

import yaml

from itertools import product

import json
import pytest
import urllib.request

from django.http import HttpResponse

from egsim.api.forms.flatfile import FlatfileMetadataInfoForm, FlatfileValidationForm
from egsim.api.forms.residuals import ResidualsForm
from egsim.api.forms.scenarios import PredictionsForm
from egsim.app.forms import (FlatfileVisualizeForm, PredictionsVisualizeForm,
                             ResidualsVisualizeForm)

from egsim.app.views import URLS, img_ext, form2dict
from django.test.client import Client

from egsim.smtk import get_sa_limits
from egsim.smtk.registry import Clabel

GSIM, IMT = 'gsim', 'imt'


tests_are_not_online = False
try:
    with urllib.request.urlopen('https://egsim.gfz-potsdam.de/') as response:
        pass  # response.read(1)
except URLError as exc:
    tests_are_not_online = True


def is_web_page_url(url: str):
    return url.startswith('WEBPAGE_')


@pytest.mark.django_db
class Test:
    with open(abspath(join(dirname(dirname(__file__)), 'data',
                           'test_flatfile.csv')), 'rb') as _:
        flatfile_tk_content = _.read()
        del _

    request_residuals_filepath = abspath(join(dirname(__file__), 'data',
                                              'request_residuals.yaml'))

    request_predictions_filepath = abspath(join(dirname(__file__), 'data',
                                                'request_trellis.yaml'))

    def test_from_to_json_dict(self):
        m_ = {GSIM: ['CauzziEtAl2014']}
        i_ = {IMT: ['PGA']}
        f_ = {'flatfile': 'esm_2018'}

        # REMEMBER THAT FORMS MODIFY INPLACE THE DICTS SO PASS dict({...}) as
        # 1ST ARGUMENT OTHERWISE THE FOLLOWING FORMS WILL HAVE UNDESIRED ARGS.
        # Test this (remove if in the future the form will copy its dicts):
        tmp = m_ | i_
        keyz = len(tmp)
        PredictionsForm(tmp)
        assert len(tmp) > keyz

        # Now check that forms are json serializable:
        for form in [
            PredictionsForm(m_ | i_),
            ResidualsForm(m_ | i_ | f_),
            FlatfileMetadataInfoForm(dict(m_)),
            FlatfileValidationForm(dict(f_)),
            FlatfileVisualizeForm(f_ | {'x': 'mag'})
        ]:
            val = form2dict(form, compact=False)
            val_c = form2dict(form, compact=True)
            # test everything is json serializable:
            _ = json.dumps(val)
            _ = json.dumps(val_c)

            p_names = sorted(form.param_name_of(n) for n in form.declared_fields)
            assert not set(val_c) - set(p_names)
            assert not set(val) - set(p_names)
            assert len(p_names) >= len(val) >= len(val_c)

    def test_html_pages(self, client):
        page_urls = [getattr(URLS, _) for _ in dir(URLS) if is_web_page_url(_)]
        assert len(page_urls)  # in case we rename the attrs sometime
        for url in page_urls:

            # external link, just check the link ios n ot broken:
            if url.startswith('http://') or url.startswith('https://'):
                continue  # see below

            # just the URL without leading slash returns 404 (TODO document why?)
            response = client.get(f"{url}" , follow=True)
            assert response.status_code == 404

            # leading
            response = client.get(f"/{url}", follow=True)
            assert response.status_code == 200

            # trailing slash al;so work (see urls.py)
            response = client.get(f"/{url}/", follow=True)
            assert response.status_code == 200

    @pytest.mark.skipif(tests_are_not_online, reason='no internet connection')
    def test_external_urls_are_not_dead(self):
        page_urls = [getattr(URLS, _) for _ in dir(URLS) if is_web_page_url(_)]
        assert len(page_urls)  # in case we rename the attrs sometime
        for url in page_urls:
            # external link, just check the link ios n ot broken:
            if url.startswith('http://') or url.startswith('https://'):
                with urllib.request.urlopen(url) as response:
                    assert response.code == 200

    def test_download_predictions_residuals(self):
        tests = [
            (
                URLS.DOWNLOAD_PREDICTIONS_DATA,
                self.request_predictions_filepath,
                PredictionsForm,
                {}
            ),
            (
                URLS.DOWNLOAD_RESIDUALS_DATA,
                self.request_residuals_filepath,
                ResidualsForm,
                {'data-query': 'mag > 7'}
            )
        ]
        for (url, yaml_filepath, form, additional_data), file_ext in \
                product(tests, ['hdf', 'csv']):
            with open(yaml_filepath) as _:
                data = yaml.safe_load(_)
            data |= additional_data
            data['format'] = file_ext
            client = Client()
            response = client.post(
                f"/{url}.{file_ext}",
                json.dumps(data),
                content_type="application/json"
            )
            assert response.status_code == 200
            content = b''.join(response.streaming_content)
            if file_ext == 'csv':
                assert len(content)
                csv = pd.read_csv(BytesIO(content))
            else:
                file_tmp_hdf = yaml_filepath + '.tmp.hdf_'
                try:
                    with open(file_tmp_hdf, 'wb') as _:
                        _.write(content)
                    hdf = pd.read_hdf(file_tmp_hdf)
                finally:
                    if isfile(file_tmp_hdf):
                        os.remove(file_tmp_hdf)

    def test_flatfile_validate(self):
        url = URLS.FLATFILE_VALIDATION

        ff = SimpleUploadedFile(
            'flatfile',
            self.flatfile_tk_content
        )
        data = {'flatfile': ff}
        client = Client()  # do not use the fixture client as we want
        # to disable CSRF Token check
        response = client.post("/" + url, data=data)
        assert response.status_code == 200
        cols1 = response.json()['columns']
        assert len(cols1) == 150

        # now try with a bigger flatfile (Django does not use a InMemory uploaded
        # file, we want to check everything is read properly anyway):
        # Build a "double sized" file content:
        csv = (
                self.flatfile_tk_content +
                b'\n'.join(self.flatfile_tk_content.split(b'\n')[1:])
        )
        ff = SimpleUploadedFile('flatfile', csv)
        data = {'flatfile': ff}
        client = Client()  # do not use the fixture client as we want
        # to disable CSRF Token check
        response = client.post("/" + url, data=data)
        assert response.status_code == 200
        cols2 = response.json()['columns']
        assert sorted(_['name'] for _ in cols1) == sorted(_['name'] for _ in cols2)

    @staticmethod
    def error_message(response: HttpResponse):
        return response.content.decode(response.charset)

    def test_flatfile_compilation_info(self):
        url = URLS.SUBMIT_FLATFILE_COMPILATION_INFO

        data = {'gsim': 'CauzziEtAl2014'}
        client = Client()  # do not use the fixture client as we want
        # to disable CSRF Token check
        response = client.post("/" + url, data=data)
        assert response.status_code == 200
        cols1 = response.json()['columns']

    def test_flatfile_visualization(self):
        url = URLS.SUBMIT_FLATFILE_VISUALIZATION

        ff = SimpleUploadedFile('flatfile', self.flatfile_tk_content)
        data = {'flatfile': ff}
        client = Client()  # do not use the fixture client as we want
        # to disable CSRF Token check
        response = client.post("/" + url, data=data)
        assert response.status_code == 400  # no x and y
        msg = self.error_message(response)
        assert "x" in msg and 'y' in msg

        for data in [
            {'x': 'mag'},  # this returns 400 cause "mag" is not in the flatfile
            {'x': 'magnitude'},
            {'x': 'PGA'},
            {'x': 'magnitude', 'y': 'PGA'},
            {'y': 'magnitude', 'x': 'PGA'}
        ]:
            ff = SimpleUploadedFile('flatfile', self.flatfile_tk_content)
            data['flatfile'] = ff  # noqa
            client = Client()  # do not use the fixture client as we want
            # to disable CSRF Token check
            response = client.post("/" + url, data=data)
            if 'mag' in data.values():
                expected_code = 400
            else:
                expected_code = 200
            assert response.status_code == expected_code

    def test_submit_predictions_residuals_visualization(self):
        tests = [
            *[(
                URLS.SUBMIT_PREDICTIONS_VISUALIZATION,
                self.request_predictions_filepath,
                PredictionsVisualizeForm,
                {'plot_type': c[0]}
            ) for c in PredictionsVisualizeForm.declared_fields['plot_type'].choices],
            (
                URLS.SUBMIT_RESIDUALS_VISUALIZATION,
                self.request_residuals_filepath,
                ResidualsVisualizeForm,
                {'data-query': 'mag > 7'}  # no x or x None => residuals
            ),
            (
                URLS.SUBMIT_RESIDUALS_VISUALIZATION,
                self.request_residuals_filepath,
                ResidualsVisualizeForm,
                # no x or x None but likelihood => LH residuals:
                {'data-query': 'mag > 7', 'likelihood': True}
            ),
            (
                URLS.SUBMIT_RESIDUALS_VISUALIZATION,
                self.request_residuals_filepath,
                ResidualsVisualizeForm,
                {'data-query': 'mag > 7', 'x': 'mag'}
            )
        ]
        for url, yaml_filepath, form, additional_data in tests:
            with open(yaml_filepath) as _:
                data = yaml.safe_load(_)
            data |= additional_data
            client = Client()
            response = client.post(f"/{url}",
                                   json.dumps(data),
                                   content_type="application/json")
            if form is PredictionsVisualizeForm and additional_data['plot_type'] == 's':
                # only SA(period) allowed, response has also other IMTs, so:
                assert response.status_code == 400
                assert 'SA' in self.error_message(response)
            else:
                assert response.status_code == 200
                assert len(response.json())

        # test errors:
        tests = [
            (
                URLS.SUBMIT_PREDICTIONS_VISUALIZATION,
                self.request_predictions_filepath,
                PredictionsVisualizeForm,
                {'plot_type': '?'}
            ),
            (
                URLS.SUBMIT_RESIDUALS_VISUALIZATION,
                self.request_residuals_filepath,
                ResidualsVisualizeForm,
                {'x': '?', 'data-query': 'mag > 7'}
            )
        ]
        for url, yaml_filepath, form, additional_data in tests:
            with open(yaml_filepath) as _:
                data = yaml.safe_load(_)
            data |= additional_data
            client = Client()
            response = client.post(f"/{url}",
                                   json.dumps(data),
                                   content_type="application/json")
            assert response.status_code == 400
            assert len(self.error_message(response))

        # test a case where the flatfile has only one row, it should not raise:
        client = Client()
        data = {
            'model': ['CauzziEtAl2014', 'BindiEtAl2014Rjb'],
            'imt': ['PGA'],
            'flatfile': 'esm2018',
            'flatfile-query': 'mag > 7.399'
        }
        response = client.post(f"/{URLS.SUBMIT_RESIDUALS_VISUALIZATION}",
                               json.dumps(data),
                               content_type="application/json")
        assert response.status_code == 200
        resp = response.json()
        # with only one point, no bins to display, so zero pts:
        for plot in resp['plots']:
            for trace in plot['data']:
                assert len(trace['y']) == len(trace['x']) == 0

        # now check with no data:
        data['flatfile-query'] = 'mag > 100'
        response = client.post(f"/{URLS.SUBMIT_RESIDUALS_VISUALIZATION}",
                               json.dumps(data),
                               content_type="application/json")
        assert response.status_code == 400

    def test_predictions_visualize_no_missing_plots(self):
        """
        Some models do not produce plots for specific IMTs or residuals type
        Test that we return those plots, albeit empty
        """
        client = Client()
        # SgobbaEtAl not defined for the given SA, AbrahmsonSilva only for total
        models = ['SgobbaEtAl2020', 'AbrahamsonSilva1997']
        imts = ['SA(0.1)', 'PGA']
        data = {
            'model': models,
            'imt': imts,
            'magnitude': [4],
            'distance': [10]
        }
        response1 = client.post(f"/{URLS.DOWNLOAD_PREDICTIONS_DATA}.csv",
                                json.dumps(data | {'format': 'csv'}),
                                content_type="application/json")
        assert response1.status_code == 200
        content = b''.join(response1.streaming_content)
        dframe = pd.read_csv(BytesIO(content), index_col=0, header=0)
        assert f'SA(0.1) {Clabel.median} SgobbaEtAl2020' not in dframe.columns
        assert f'SA(0.1) {Clabel.std} AbrahamsonSilva1997' in dframe.columns
        assert f'PGA {Clabel.median} SgobbaEtAl2020' in dframe.columns
        assert f'SA(0.1) {Clabel.median} AbrahamsonSilva1997' in dframe.columns
        # 2 imts for SgobbaEtAl, 4 for Abrahamson et al:
        len_c = len([c for c in dframe.columns if not c.startswith(f'{Clabel.input} ')])
        assert len_c == 6

        response = client.post(f"/{URLS.SUBMIT_PREDICTIONS_VISUALIZATION}",
                               json.dumps(data | {'plot_type': 'm'}),
                               content_type="application/json")
        assert response.status_code == 200
        json_c = response.json()
        plots = json_c['plots']
        # first plot has 6 traces (3 Sgobba, 3 Abrhamson)
        # second plot has 3 tracs (3 Abrhamson, Sgobba non-implemented for SA)
        # the 3 plots per model is because we also have std (upper and lower bound)
        assert (len(plots[0]['data']) == 6 and len(plots[1]['data']) == 3) or \
            (len(plots[1]['data']) == 6 and len(plots[0]['data']) == 3)

    def test_predictions_visualize_missing_periods_no_exc(self):
        """
        Some models do not produce plots for specific IMTs or residuals type
        Test that we return those plots, albeit empty
        """
        client = Client()
        # SgobbaEtAl not defined for the given SA, AbrahmsonSilva only for total
        models = ['SgobbaEtAl2020', 'BindiEtAl2014Rjb']
        imts = [f'SA({_})' for _ in [0.01, 0.015, 0.5, 0.6]]
        data = {
            'model': models,
            'imt': imts,
            'magnitude': [4],
            'distance': [10]
        }
        saLim1 = get_sa_limits('SgobbaEtAl2020')
        salim2 = get_sa_limits('BindiEtAl2014Rjb')
        response = client.post(f"/{URLS.SUBMIT_PREDICTIONS_VISUALIZATION}",
                               json.dumps(data | {'plot_type': 's'}),
                               content_type="application/json")
        assert response.status_code == 200
        json_c = response.json()
        plots = json_c['plots']
        # only one plot (one dist and one mag):
        assert len(plots) == 1
        # 3 plots for Bindi, 3 for Sgobba (medians + stdev x2 ) x2:
        assert len(plots[0]['data']) == 6
        data = plots[0]['data']
        # all x values should amtch the sa limits of the models, which are
        # 0.5 and 0.6 for both:
        assert all(d['x'] == [0.5, 0.6] for d in data)

    def test_residuals_visualize_no_missing_plots(self):
        """
        Some models do not produce plots for specific IMTs or residuals type
        Test that we return those plots, albeit empty
        """
        client = Client()
        # SgobbaEtAl not defined for the given SA, AbrahmsonSilva only for total
        models = ['SgobbaEtAl2020', 'AbrahamsonSilva1997']
        imts = ['SA(0.1)', 'PGA']
        data = {
            'model': models,
            'imt': imts,
            'flatfile': 'esm2018',
            'flatfile-query': 'mag > 7'
        }
        saLim1 = get_sa_limits('SgobbaEtAl2020')
        salim2 = get_sa_limits('AbrahamsonSilva1997')
        response1 = client.post(f"/{URLS.DOWNLOAD_RESIDUALS_DATA}.csv",
                                json.dumps(data | {'format': 'csv'}),
                                content_type="application/json")
        assert response1.status_code == 200
        content = b''.join(response1.streaming_content)
        dframe = pd.read_csv(BytesIO(content), index_col=0, header=0)
        assert f'SA(0.1) {Clabel.total_res} SgobbaEtAl2020' not in dframe.columns
        assert f'SA(0.1) {Clabel.intra_ev_res} AbrahamsonSilva1997' not in dframe.columns
        assert f'PGA {Clabel.total_res} SgobbaEtAl2020' in dframe.columns
        assert f'SA(0.1) {Clabel.total_res} AbrahamsonSilva1997' in dframe.columns
        # 3 imts for SgobbaEtAl, 2 for Abrahamson et al:
        len_c = len([c for c in dframe.columns if not c.startswith(f'{Clabel.input} ')])
        assert len_c == 5

        response = client.post(f"/{URLS.SUBMIT_RESIDUALS_VISUALIZATION}",
                               json.dumps(data),
                               content_type="application/json")
        assert response.status_code == 200
        expected_params = set(
            product(imts, models, ('Total', 'Inter event', 'Intra event'))
        )
        json_c = response.json()
        plots = json_c['plots']
        actual_params = {
            (c['params']['imt'], c['params']['model'], c['params']['residual type'])
            for c in plots
        }
        assert len(actual_params) == 12
        assert expected_params == actual_params

    def test_download_response_img_formats(self):
        for url, ext in product((URLS.DOWNLOAD_PREDICTIONS_PLOT,
                                 URLS.DOWNLOAD_RESIDUALS_PLOT),
                                img_ext):
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
            # to disable CSRF Token check
            response = client.post(f"/{url}.{ext}",
                                   json.dumps({'data': data, 'layout': layout,
                                               'width': 100, 'height': 100}),
                                   content_type="application/json")
            content = b''.join(response.streaming_content)
            assert response.status_code == 200
            if ext == 'png':
                assert b'PNG' in content[:5]
            elif ext == 'pdf':
                assert b'PDF' in content[:5]
            elif ext == 'svg':
                assert b'<svg ' in content[:5]
            else:
                raise ValueError(f'content generated for image format {ext} not tested')

    def test_downloaded_data_tutorials(self):
        for url in (
                URLS.PREDICTIONS_DOWNLOADED_DATA_TUTORIAL,
                URLS.RESIDUALS_DOWNLOADED_DATA_TUTORIAL):
            client = Client()  # do not use the fixture client as we want
            response = client.post(f"/{url}", {}, content_type="text/html")
            assert response.status_code == 200
            assert response.content.strip().startswith(b'<!DOCTYPE html>')

    def test_oq_version(self):
        """
        Test oq_version matches. Because we do provide our 'oq_version' global
        variable to speedup HTML page rendering in egsim.app.views, we need to be
        sure it matches current OQ version """
        from openquake.engine import __version__ as real_oq_version
        from egsim.app.views import oq_version as egsim_claimed_oq_version
        assert real_oq_version == egsim_claimed_oq_version

        # if the test above fails, also change this:!!!
        from egsim.app.views import oq_gmm_refs_page
        assert oq_gmm_refs_page == \
               "https://docs.openquake.org/oq-engine/3.15/reference/"

    def test_select_models_from_region(self):
        """
        Test the models selection via map clicks. Use US because more borderline case
        """
        client = Client()  # do not use the fixture client as we want
        url = URLS.GSIMS_FROM_REGION

        response = client.post(
            f"/{url}",
            json.dumps({'lat': 35, 'lon': -116}),
            content_type="application/json"
        )
        assert response.status_code == 200
        assert len(response.json()['models']) == 0

        response = client.post(
            f"/{url}",
            json.dumps({'lat': 50, 'lon': 20}),
            content_type="application/json"
        )
        assert response.status_code == 200
        resp_data = response.json()['models']
        for mod in ["AkkarBommer2010","CauzziFaccioli2008","ChiouYoungs2008","ZhaoEtAl2006Asc","ESHM20Craton"]:
            assert resp_data.pop(mod) == ['share']
        assert not resp_data

        # this view does not raise even when errors are provided:
        response = client.post(
            f"/{url}",
            json.dumps({}),  # <- no params, error in principle (not in this view)
            content_type="application/json"
        )
        assert response.status_code == 200
        assert response.json()['models'] == {}
