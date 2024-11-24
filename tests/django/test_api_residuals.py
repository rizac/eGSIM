"""
Tests the client for the residuals service API

Created on 22 Oct 2018

@author: riccardo
"""
from os.path import dirname, join, abspath
from io import BytesIO
import yaml
import numpy as np
import pandas as pd
import pytest

from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.utils.datastructures import MultiValueDict

from egsim.api.urls import RESIDUALS_URL_PATH
from egsim.api.views import (ResidualsView, APIFormView, as_querystring,
                             read_df_from_csv_stream, read_df_from_hdf_stream,
                             write_df_to_hdf_stream)
from egsim.smtk import read_flatfile
from egsim.smtk.converters import dataframe2dict
from egsim.smtk.registry import Clabel


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

    @staticmethod
    def error_message(response: HttpResponse):
        return response.content.decode(response.charset)

    def test_uploaded_flatfile(self,
                               # pytest fixtures:
                               client):
        with open(self.request_filepath) as _:
            inputdic = yaml.safe_load(_)

        # Uploaded flatfile, but not well-formed:
        # column in data-query not defined:
        csv = SimpleUploadedFile("file.csv", b"PGA,b,c,d\n1.1,,,", 
                                 content_type="text/csv")
        inputdic2 = dict(inputdic, flatfile=csv)
        # test wrong flatfile:
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 400
        assert self.error_message(resp2) == "data-query: name 'vs30' is not defined"

        # 1b no rows matching query:
        csv = SimpleUploadedFile("file.csv", b"PGA,vs30,mag,b,c,d\n1.1,,,",
                                 content_type="text/csv")
        inputdic2 = dict(inputdic, flatfile=csv)
        # test wrong flatfile:
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 400
        assert self.error_message(resp2) == "data-query: no rows matching query"

        # 1c missing ground motion properties:
        csv = SimpleUploadedFile("file.csv", b"PGA,vs30,mag,b,c,d\n1.1,,,",
                                 content_type="text/csv")
        inputdic2 = dict(inputdic, flatfile=csv)
        inputdic2.pop('data-query')  # to avoid adata-query errors (already checked)
        # test wrong flatfile:
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 400
        assert self.error_message(resp2) == "flatfile: missing column(s) PGV"

        # 1d missing ground motion properties (2):
        csv = SimpleUploadedFile("file.csv", b"PGA,PGV,vs30,mag,b,c,d\n1.1,,,",
                                 content_type="text/csv")
        inputdic2 = dict(inputdic, flatfile=csv)
        inputdic2.pop('data-query')  # to avoid adata-query errors (already checked)
        # test wrong flatfile:
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 400
        assert self.error_message(resp2) == \
               ("flatfile: missing column(s) SA(period_in_s) (columns found: 0, "
                f'at least two are required)')

        # 1d missing ground motion properties (2):
        csv = SimpleUploadedFile("file.csv", b"PGA,PGV,SA(0.2),vs30,mag,b,c,d\n1.1,,,",
                                 content_type="text/csv")
        inputdic2 = dict(inputdic, flatfile=csv)
        inputdic2.pop('data-query')  # to avoid adata-query errors (already checked)
        # test wrong flatfile:
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 400
        assert self.error_message(resp2) == \
               "flatfile: missing column(s) rake, rjb"

        # 3 dupes:
        csv = SimpleUploadedFile("file.csv", b"CAV,hypo_lat,evt_lat,d\n1.1,,,",
                                 content_type="text/csv")
        inputdic2 = dict(inputdic, flatfile=csv)
        # test wrong flatfile:
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 400
        # account for different ordering in error columns:
        assert self.error_message(resp2) in \
               ("flatfile: column names conflict evt_lat, hypo_lat",
                "flatfile: column names conflict hypo_lat, evt_lat")

        def fake_post(self, request):  # noqa
            # Django testing class `client` expects every data in the `data` argument
            # whereas Django expects two different arguments, `data` and `files`
            # this method simply bypasses the files renaming (from the user provided
            # flatfile into 'uploaded_flatfile' in the Form) and calls directly :
            return ResidualsView().response(request,
                                            data=dict(inputdic2, flatfile='esm2018'),
                                            files=MultiValueDict({'flatfile': csv}))

        with patch.object(APIFormView, 'post', fake_post):
            resp2 = client.post(self.url, data=inputdic2)
            assert resp2.status_code == 400
            assert 'flatfile' in self.error_message(resp2)

        # 4 missing column error (PGV):
        csv = SimpleUploadedFile("file.csv", (b"PGA;rake;rjb;vs30;hypo_lat;mag\n"
                                              b"1.1;1;1;1;1;1;1"),
                                 content_type="text/csv")
        inputdic2 = dict(inputdic, flatfile=csv)
        inputdic2.pop('data-query')
        # test wrong flatfile:
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 400
        # account for different ordering in error columns:
        assert self.error_message(resp2) == 'flatfile: missing column(s) PGV'

        # 5 missing column error (event id):
        csv = SimpleUploadedFile("file.csv",
                                 (b"PGA;PGV;SA(0.2);rake;rjb;vs30;hypo_lat;mag\n"
                                  b"1.1;1;1;1;1;1;1;1;0"),
                                 content_type="text/csv")
        inputdic2 = dict(inputdic, flatfile=csv)
        inputdic2.pop('data-query')
        # test wrong flatfile:
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 400
        # account for different ordering in error columns:
        assert self.error_message(resp2) == 'flatfile: missing column(s) evt_id'

    def test_upload_hdf(self, client, settings):  # <- both pytest-django fixutures
        """As of pandas 2.2.2, HDF cannot be read from buffer but only from file.
        Test this here
        """

        # FIRST we test that the current pandas version does NOT support
        # upload from file
        dfr = pd.read_csv(BytesIO(self.flatfile_tk_content))
        bytes_io = write_df_to_hdf_stream({'egsim': dfr})
        with pytest.raises(Exception) as exc:
            read_flatfile(bytes_io)

        hdf = SimpleUploadedFile("file.csv",
                                 bytes_io.getvalue(),
                                 content_type="text/csv")
        inputdic2 = {
            'model': 'KothaEtAl2020ESHM20',
            'imt': 'PGA',
            'flatfile': hdf
        }
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 200

        # test that hdf does not work from buffer. To do so, assure Django will NOT
        # write data to disk by modifying settings temporarily
        settings.FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * len(bytes_io.getvalue())
        hdf = SimpleUploadedFile("file.csv",
                                 bytes_io.getvalue(),
                                 content_type="text/csv")
        inputdic2 = {
            'model': 'KothaEtAl2020ESHM20',
            'imt': 'PGA',
            'flatfile': hdf
        }
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 500

    def test_kotha_turkey(self, client):
        csv = SimpleUploadedFile("file.csv",
                                 self.flatfile_tk_content,
                                 content_type="text/csv")
        inputdic2 = {
            'model': 'KothaEtAl2020ESHM20',
            'imt': 'PGA',
            'flatfile': csv
        }
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 200

    def test_cauzzi_rjb_turkey(self, client):
        csv = SimpleUploadedFile("file.csv",
                                 self.flatfile_tk_content,
                                 content_type="text/csv")
        inputdic2 = {
            'model': 'CauzziEtAl2014',
            'imt': 'PGA',
            'flatfile': csv
        }
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 200

    def test_cauzzi_vs30_turkey(self, client):
        csv = SimpleUploadedFile("file.csv",
                                 self.flatfile_tk_content,
                                 content_type="text/csv")
        inputdic2 = {
            'model': 'CauzziEtAl2014',
            'imt': 'PGA',
            'flatfile': csv,
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
            'imt': 'PGA',
            'flatfile': csv,
            'multi_header': True
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
            'multi_header': True
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
        assert self.error_message(resp1) == 'flatfile: missing parameter is required'

        # test conflicting values:
        resp1 = client.get(self.querystring({
            **inputdic,
            'selection-expression': '(vs30 > 800) & (vs30 < 1200)',
            'data-query': '(vs30 > 1000) & (vs30 < 1010)'
        }))
        assert resp1.status_code == 400
        assert 'data-query' in self.error_message(resp1)

        inputdic['data-query'] = '(magnitude >5'
        resp2 = client.post(self.url, data=inputdic, content_type='application/json')
        resp1 = client.get(self.querystring(inputdic))
        assert resp1.status_code == resp2.status_code == 400
        err_msg = self.error_message(resp1)
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

        resp_json = None
        for format in [None, 'csv', 'hdf']:
            if format is None:
                inputdic.pop('format', None)
            else:
                inputdic['format'] = format

            resp2 = client.post(
                self.url, data=inputdic, content_type='application/json')

            assert resp2.status_code == 200
            content = BytesIO(resp2.getvalue())
            if format is None:  # format defaults to JSON
                resp_json = resp1.json()
                continue
            dfr2 = read_df_from_csv_stream(content, header=[0, 1, 2]) \
                if format == 'csv' \
                else read_df_from_hdf_stream(content)
            new_json = dataframe2dict(dfr2)
            assert np.allclose(
                resp_json['SA(0.2)'][Clabel.total_res]['BindiEtAl2011'],
                new_json['SA(0.2)'][Clabel.total_res]['BindiEtAl2011'])
            assert np.allclose(
                resp_json['PGA'][Clabel.total_res]['BindiEtAl2014Rjb'],
                new_json['PGA'][Clabel.total_res]['BindiEtAl2014Rjb'])
            # assert resp_json == dataframe2dict(dfr2)

    def test_residuals_service_single_multi_header(self,
                                                   # pytest fixtures:
                                                   client):
        with open(self.request_filepath) as _:
            inputdic = yaml.safe_load(_)
        inputdic['data-query'] = '(vs30 >= 1000) & (mag>=7)'

        inputdic['format'] = 'hdf'
        resp = client.post(self.url, data=inputdic, content_type='application/json')
        assert resp.status_code == 200
        result_hdf = read_df_from_hdf_stream(BytesIO(b''.join(resp.streaming_content)))

        inputdic.pop('multi_header')
        resp = client.post(self.url, data=inputdic, content_type='application/json')
        assert resp.status_code == 200
        result_hdf_single_header = (
            read_df_from_hdf_stream(BytesIO(b''.join(resp.streaming_content)))
        )

        # check two dataframes are equal
        assert len(result_hdf.columns) == len(result_hdf_single_header.columns)
        result_hdf.columns = [Clabel.sep.join(c) for c in result_hdf.columns]  # noqa
        pd.testing.assert_frame_equal(result_hdf, result_hdf_single_header)

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
        assert resp1.status_code == 400
        assert self.error_message(resp1) == 'plot: unknown parameter'

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
            'format': 'hdf',
            'multi_header': True
        }
        resp1 = client.get(self.url, data=inputdict,
                           content_type='application/json')
        assert resp1.status_code == 200
        dfr = read_df_from_hdf_stream(BytesIO(resp1.getvalue()))
        inter_ev_values = dfr[('SA(0.1)', 'inter_event_residual', 'BooreEtAl2014')]
        # this was before converting SA to g:
        # assert 13 < inter_ev_values.median() < 14
        # now it should be:
        q1, m, q9 = inter_ev_values.quantile([.1, .5, .9])
        assert -1.5 < m < -1

        # now with no norm:
        resp1 = client.get(self.url, data=inputdict | {'normalize': False},
                           content_type='application/json')
        assert resp1.status_code == 200
        dfr = read_df_from_hdf_stream(BytesIO(resp1.getvalue()))
        inter_ev_values = dfr[('SA(0.1)', 'inter_event_residual', 'BooreEtAl2014')]
        q1_nonorm, m_nonomr, q9_nonorm = inter_ev_values.quantile([.1, .5, .9])
        assert -1 < m_nonomr < -.5

    def test_residuals_ranking(self,
                               # pytest fixtures:
                               client):
        with open(self.request_filepath) as _:
            inputdic = yaml.safe_load(_)
        inputdic['data-query'] = '(vs30 >= 1000) & (mag>=7)'
        inputdic['ranking'] = True

        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(self.querystring(inputdic))
        assert resp1.status_code == 200
        assert resp1.json() == resp2.json()

        resp_json = None
        for format in [None, 'csv', 'hdf']:
            if format is None:
                inputdic.pop('format', None)
            else:
                inputdic['format'] = format

            inputdic.pop('likelihood', None)
            inputdic.pop('normalize', None)
            resp2 = client.post(
                self.url, data=inputdic, content_type='application/json')
            assert resp2.status_code == 200
            if format is None:
                resp_json = resp2.json()
                continue

            content = resp2.getvalue()
            # if prev_content is None:
            #     prev_content = content
            # else:
            #     assert prev_content == content
            dfr2 = read_df_from_csv_stream(BytesIO(content), header=0) \
                if format == 'csv' \
                else read_df_from_hdf_stream(BytesIO(content))

            assert sorted(dfr2.columns) == sorted(resp_json.keys())
            for k in resp_json.keys():
                assert sorted(resp_json[k].keys()) == sorted(dfr2[k].keys())
                assert np.allclose(
                    np.array(list(resp_json[k].values()), dtype=float),
                    dfr2[k],
                    equal_nan=True)

        # test with all possible variants of likelihood and normalize
        # parameters, as those are set by default to True, True and thus
        # results should always be the same
        with patch('egsim.api.forms.residuals.get_residuals',
                   side_effect=pd.DataFrame()) as g_res:
            for i_dict in [
                {'likelihood': False, 'normalize': False},
                {'likelihood': False, 'normalize': True},
                {'likelihood': True, 'normalize': False},
                {'likelihood': True, 'normalize': True},
               ]:
                resp2 = client.post(
                    self.url, data=inputdic | i_dict, content_type='application/json')
                args = g_res.call_args
                assert args[1]['likelihood'] is True
                assert args[1]['mean'] is True
                assert args[1]['normalise'] is True

    @patch('egsim.smtk.residuals.get_ground_motion_values', side_effect=ValueError('a'))
    def test_residuals_model_error(self,
                                   mock_get_gmv,
                                   # pytest fixtures:
                                   client):
        with open(self.request_filepath) as _:
            inputdic = yaml.safe_load(_)
        inputdic['data-query'] = '(vs30 >= 1000) & (mag>=7)'
        inputdic['ranking'] = True

        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(self.querystring(inputdic))
        assert resp1.status_code == 400
        err_msg = resp1.content
        assert err_msg == resp2.content
        expected_model = sorted(inputdic['model'])[0]
        assert mock_get_gmv.called
        assert f'{expected_model}: (ValueError) a' in str(err_msg)