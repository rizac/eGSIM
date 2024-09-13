"""
Tests the client for the residuals service API

Created on 22 Oct 2018

@author: riccardo
"""
from os.path import dirname, join, abspath
from io import BytesIO
import yaml
import pytest

from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.datastructures import MultiValueDict

from egsim.api.urls import RESIDUALS_URL_PATH
from egsim.api.views import (ResidualsView, RESTAPIView, as_querystring,
                             read_csv_from_buffer, read_hdf_from_buffer)
from egsim.smtk.converters import dataframe2dict


@pytest.mark.django_db
class Test:
    """tests the residuals service"""

    url = f"/{RESIDUALS_URL_PATH}"
    
    data_dir = abspath(join(dirname(__file__), 'data'))
    request_filepath = join(data_dir, 'request_residuals.yaml')
    
    # flatfile 1
    flatfile_bindi_content: bytes
    with open(join(data_dir, 'PGA_BindiEtAl17.csv'), 'rb') as _:
        flatfile_bindi_content = _.read()
    
    # flatfile 2 (in parent data dir because it is shared with egsim.smtk):
    flatfile_tk_content: bytes
    data_dir = join(dirname(dirname(data_dir)), 'data')
    with open(join(data_dir, 'test_flatfile.csv'), 'rb') as _:
        flatfile_tk_content = _.read()

    def querystring(self, data):
        return f'{self.url}?{as_querystring(data)}'

    def test_uploaded_flatfile(self,
                               # pytest fixtures:
                               client):
        with open(self.request_filepath) as _ :
            inputdic = yaml.safe_load(_)

        # Uploaded flatfile, but not well-formed:
        # 1 missing ground motion properties:
        csv = SimpleUploadedFile("file.csv", b"PGA,b,c,d\n1.1,,,", 
                                 content_type="text/csv")
        inputdic2 = dict(inputdic, flatfile=csv)
        # test wrong flatfile:
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 400
        assert resp2.json()['message'] == \
               "data-query: name 'vs30' is not defined; " \
               "flatfile: missing required column(s): mag, rake, rjb, vs30"
        # 2 missing compatible IMTs
        csv = SimpleUploadedFile("file.csv", b"CAV,b,c,d\n1.1,,,",
                                 content_type="text/csv")
        inputdic2 = dict(inputdic, flatfile=csv)
        # test wrong flatfile:
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 400
        assert resp2.json()['message'] == \
               ("data-query: name 'vs30' is not defined; "
                "flatfile: missing required column(s): "
                "PGA or PGV or SA, mag, rake, rjb, vs30")
        # 3 dupes:
        csv = SimpleUploadedFile("file.csv", b"CAV,hypo_lat,evt_lat,d\n1.1,,,",
                                 content_type="text/csv")
        inputdic2 = dict(inputdic, flatfile=csv)
        # test wrong flatfile:
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 400
        # account for different ordering in error columns:
        assert resp2.json()['message'] in \
               ("flatfile: column names conflict evt_lat, hypo_lat",
                "flatfile: column names conflict hypo_lat, evt_lat")

        def fake_post(self, request):
            # Django testing class `client` expects every data in the `data` argument
            # whereas Django expects two different arguments, `data` and `files`
            # this method simply bypasses the files renaming (from the user provided
            # flatfile into 'uploaded_flatfile' in the Form) and calls directly :
            return ResidualsView().response(data=dict(inputdic2, flatfile='esm2018'),
                                            files=MultiValueDict({'flatfile': csv}))

        with patch.object(RESTAPIView, 'post', fake_post):
            resp2 = client.post(self.url, data=inputdic2)
            assert resp2.status_code == 400
            assert 'flatfile' in resp2.json()['message']

    def test_kotha_turkey(self, client):
        csv = SimpleUploadedFile("file.csv",
                                 self.flatfile_tk_content,
                                 content_type="text/csv")
        inputdic2 = {
            'model': 'KothaEtAl2020ESHM20',
            'imt' : 'PGA',
            'flatfile':csv
        }
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 200

    def test_cauzzi_rjb_turkey(self, client):
        csv = SimpleUploadedFile("file.csv",
                                 self.flatfile_tk_content,
                                 content_type="text/csv")
        inputdic2 = {
            'model': 'CauzziEtAl2014',
            'imt' : 'PGA',
            'flatfile':csv
        }
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 200

    def test_cauzzi_vs30_turkey(self, client):
        csv = SimpleUploadedFile("file.csv",
                                 self.flatfile_tk_content,
                                 content_type="text/csv")
        inputdic2 = {
            'model': 'CauzziEtAl2014',
            'imt' : 'PGA',
            'flatfile':csv,
        }
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 200

    def test_bindi17_turkey(self, client):
        # Uploaded flatfile, but not well-formed:
        csv = SimpleUploadedFile("file.csv",
                                 self.flatfile_bindi_content,
                                 content_type="text/csv")
        inputdic2 = {
            'model': 'BindiEtAl2017Rhypo',
            'imt' : 'PGA',
            'flatfile':csv
        }
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 200
        resp_json = resp2.json()
        assert "PGA" in resp_json

    def test_notebook_example(self, client):
        csv = SimpleUploadedFile("file.csv",
                                 self.flatfile_tk_content,
                                 content_type="text/csv")
        inputdic2 = {
            'model': ['BindiEtAl2014Rjb', 'BooreEtAl2014'],
            'imt': ['PGA', 'SA(1.0)'],
            'flatfile': csv,
        }
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 200
        assert "SA(1.0)" in resp2.json()

    def test_residuals_service_err(self,
                                   # pytest fixtures:
                                   client):
        """tests errors in the residuals API service."""
        with open(self.request_filepath) as _:
            inputdic = yaml.safe_load(_)

        # no flatfile, uploaded flatfile:
        inputdic2 = dict(inputdic)
        inputdic2.pop('flatfile')
        resp2 = client.post(self.url, data=inputdic2,
                            content_type='application/json')
        resp1 = client.get(self.querystring(inputdic2))
        assert resp1.status_code == resp2.status_code == 400
        assert resp1.json()['message'] == 'flatfile: missing parameter is required'

        # test conflicting values:
        resp1 = client.get(self.querystring({**inputdic,
                                             'selection-expression': '(vs30 > 800) & (vs30 < 1200)',
                                             'data-query': '(vs30 > 1000) & (vs30 < 1010)'}))
        assert resp1.status_code == 400
        assert 'data-query' in resp1.json()['message']

        inputdic['data-query'] = '(magnitude >5'
        resp2 = client.post(self.url, data=inputdic, content_type='application/json')
        resp1 = client.get(self.querystring(inputdic))
        assert resp1.status_code == resp2.status_code == 400
        err_msg = resp1.json()['message']
        assert 'data-query' in err_msg
        assert 'data-query' in err_msg

        # test error give in format (text instead of csv):
        inputdict2 = dict(inputdic, format='text')
        inputdict2.pop('data-query')
        resp2 = client.post(self.url, data=inputdict2, content_type='text/csv')
        assert resp2.status_code == 400

    def test_residuals_service(self,
                                   # pytest fixtures:
                                   client):
        with open(self.request_filepath) as _:
            inputdic = yaml.safe_load(_)
        inputdic['data-query'] = '(vs30 >= 1000) & (mag>=7)'

        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(self.querystring(inputdic))
        assert resp1.status_code == 200
        assert resp1.json() == resp2.json()

        for format in [None, 'csv', 'hdf']:
            if format is None:
                inputdic.pop('format', None)
            else:
                inputdic['format'] = format

        resp2 = client.post(
            self.url, data=inputdic, content_type='application/json')

        assert resp2.status_code == 200
        content = BytesIO(resp2.getvalue())
        dfr2 = read_csv_from_buffer(content) if format == 'csv' \
            else read_hdf_from_buffer(content)
        assert resp1.json() == dataframe2dict(dfr2)

    def test_residuals_invalid_get(self,
                                   # pytest fixtures:
                                   client):
        """Tests supplying twice the plot_type (invalid) and see what
        happens. This request error can happen only from an API request, not
        from the web portal"""
        resp1 = client.get(self.url +
                           ('?gsim=BindiEtAl2014Rjb&flatfile=wrong_flatfile_name'
                            '&imt=PGA&plot=res&plot=llh'),
                           content_type='application/json')
        assert resp1.json()['message'] == 'plot: unknown parameter'
        assert resp1.status_code == 400

    def test_allen2012(self,
                       # pytest fixtures:
                       client):
        """test a case where the browser simply stops calculating without
        error messages. The cause was due to an AssertionError with empty
        message. UPDATE 2021: the case seems to be fixed now in OpenQuake"""
        inputdict = {
            "gsim": [
                "Allen2012"
            ],
            "imt": [
                "PGA"
            ],
            'flatfile': 'esm2018'
        }
        resp1 = client.get(self.url, data=inputdict,
                           content_type='application/json')
        assert resp1.status_code == 200

    def test_booreetal_esm(self,
                       # pytest fixtures:
                       client):
        """test a case where we got very strange between events (intra events)
        Bug discovered in sept 2024
        Tests also normalize parameter
        """
        inputdict = {
            "gsim": [
                "BooreEtAl2014"
            ],
            "imt": [
                "SA(0.1)"
            ],
            'flatfile': 'esm2018',
            'flatfile-query': 'rjb < 200',
            'format': 'hdf'
        }
        resp1 = client.get(self.url, data=inputdict,
                           content_type='application/json')
        assert resp1.status_code == 200
        dfr = read_hdf_from_buffer(BytesIO(resp1.getvalue()))
        inter_ev_values = dfr[('SA(0.1)', 'inter_event_residual', 'BooreEtAl2014')]
        # this was before comnverting SA to g:
        # assert 13 < inter_ev_values.median() < 14
        # now it should be:
        q1, m, q9 = inter_ev_values.quantile([.1, .5, .9])
        assert -1.5 < m < -1

        # now with no norm:
        resp1 = client.get(self.url, data=inputdict | {'normalize': False},
                           content_type='application/json')
        assert resp1.status_code == 200
        dfr = read_hdf_from_buffer(BytesIO(resp1.getvalue()))
        inter_ev_values = dfr[('SA(0.1)', 'inter_event_residual', 'BooreEtAl2014')]
        q1_nonorm, m_nonomr, q9_nonorm =  inter_ev_values.quantile([.1, .5, .9])
        assert -1 < m_nonomr < -.5
