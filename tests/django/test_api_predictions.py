"""
Tests the client for the trellis service API

Created on 2 Jun 2018

@author: riccardo
"""
from os.path import dirname, join, abspath

from io import BytesIO

import pandas as pd
import yaml

import pytest
import numpy as np
from django.http import HttpResponse
from openquake.hazardlib.gsim.akkar_2014 import AkkarEtAlRjb2014

from egsim.api.urls import PREDICTIONS_URL_PATH
from egsim.api.views import (MimeType, read_df_from_hdf_stream,
                             read_df_from_csv_stream, as_querystring)
from egsim.api.forms.scenarios import PredictionsForm

from unittest.mock import patch  # ok in py3.8  # noqa

from egsim.smtk import registered_imts
from egsim.smtk.flatfile import ColumnType
from egsim.smtk.registry import imt_name, Clabel


@pytest.mark.django_db
class Test:
    """tests the gsim service"""

    url = f"/{PREDICTIONS_URL_PATH}"
    request_filepath = abspath(join(dirname(__file__), 'data', 'request_trellis.yaml'))

    def querystring(self, data):
        return f'{self.url}?{as_querystring(data)}'

    @staticmethod
    def error_message(response: HttpResponse):
        return response.content.decode(response.charset)

    # @pytest.mark.parametrize('st_dev', [False, True])
    def test_trellis(
            self,
            # pytest fixtures:
            client):
        """test trellis distance and distance stdev"""
        with open(self.request_filepath) as _:
            inputdic = dict(yaml.safe_load(_))

        # and from now on,
        resp1 = client.get(self.querystring(inputdic))
        resp2 = client.post(self.url, data=inputdic,
                            content_type=MimeType.json)
        assert resp1.status_code == resp2.status_code == 200
        result = resp1.json()
        assert result == resp2.json()
        form = PredictionsForm(data=dict(inputdic))
        assert form.is_valid()
        # input_ = form.cleaned_data
        assert sorted(result.keys()) == ['PGA', 'PGV', 'SA(0.2)', Clabel.input]
        # assert list(result.keys())[1] == 'rrup'
        mags = result[Clabel.input][ColumnType.rupture.value]['mag']
        dists = result[Clabel.input][ColumnType.distance.value]['rrup']
        assert len(mags) == len(dists) == 12
        result_json = result

        # test the hdf response:
        resp = client.post(self.url, data=dict(inputdic, format="hdf"),
                           content_type=MimeType.hdf)
        assert resp.status_code == 200
        result_hdf = read_df_from_hdf_stream(BytesIO(b''.join(resp.streaming_content)))

        # test the text/csv response:
        resp = client.post(self.url, data=dict(inputdic, format="csv"),
                           content_type=MimeType.csv)
        assert resp.status_code == 200
        result_csv = read_df_from_csv_stream(
            BytesIO(b''.join(resp.streaming_content)),
            header=[0, 1, 2]
        )

        assert sorted(result_csv.columns) == sorted(result_hdf.columns)

        for col in result_csv.columns:
            assert (result_csv[col] == result_hdf[col]).all() or \
                np.allclose(result_csv[col], result_hdf[col],
                            rtol=1.e-12, atol=0, equal_nan=True)
            if col[-1]:  # not ('mag', '', '') or ('rrup, '', ''),
                # but computed trellis data (e.g. ('PGA', 'median', 'model_name')):
                result_json_col = result_json[col[0]][col[1]][col[2]]
            else:
                result_json_col = result_json[col[0]]
            assert (result_csv[col] == result_json_col).all() or \
                np.allclose(result_csv[col], result_json_col,
                            rtol=1.e-12, atol=0, equal_nan=True)

    def test_trellis_single_multi_header(
            self,
            # pytest fixtures:
            client):
        with open(self.request_filepath) as _:
            inputdic = dict(yaml.safe_load(_))
        inputdic['format'] = 'hdf'

        # test the hdf response:
        resp = client.post(self.url, data=dict(inputdic, format="hdf"),
                           content_type=MimeType.json)
        assert resp.status_code == 200
        result_hdf = read_df_from_hdf_stream(BytesIO(b''.join(resp.streaming_content)))

        inputdic.pop('multi_header')
        resp = client.post(self.url, data=inputdic, content_type=MimeType.json)
        assert resp.status_code == 200
        result_hdf_single_header = read_df_from_hdf_stream(
            BytesIO(b''.join(resp.streaming_content)))

        # check two dataframes are equal
        assert len(result_hdf.columns) == len(result_hdf_single_header.columns)
        result_hdf.columns = [Clabel.sep.join(c) for c in result_hdf.columns]  # noqa
        pd.testing.assert_frame_equal(result_hdf, result_hdf_single_header)

    def test_400_invalid_param_names(self,
                                     # pytest fixtures:
                                     client):
        """Test invalid param names in request"""
        data = {
            'aspect': 1,
            'backarc': False,
            'dip': 60,
            'distance': [10, 50, 100],
            'gsim': ["AkkarEtAlRjb2014", "BindiEtAl2014Rjb", "BooreEtAl2014"],
            'hypoloc': "0.5 0.5",  # invalid name
            'lineazimuth': 0,  # invalid name
            'location': [0, 0],  # invalid name
            "magnitude": [5, 6, 7],
            "msr": "WC1994",
            # "plot": "s",
            "rake": 0,
            # "stdev": False,
            "strike": 0,
            "vs30": 760,
            "vs30measured": True,
            "z1": None,
            "z2pt5": None,
            "ztor": 0
        }
        resp = client.post(self.url, data=data,
                           content_type='application/json')
        assert resp.status_code == 400

    def test_error(self,
                   # pytest fixtures:
                   client):
        """tests a special case where we supply a deprecated gsim (not in
        EGSIM list)"""
        inputdic = {
            "gsim": ["AkkarEtAl2013", "AkkarEtAlRepi2014"],
            "imt": ["PGA", "PGV"],
            "magnitude": [3, 4],  # "3:4",
            "distance": [10, 11, 12],  # "10:12",
            "dip": "60",
            "aspect": "1.5",
            "rake": "0.0",
            "ztor": "0.0",
            "strike": "0.0",
            "msr": "WC1994",
            "initial_point": [0, 0],
            "hypocentre_location": [0.5, 0.5],
            "vs30": "760.0",
            "vs30_measured": True,
            "line_azimuth": "0.0",
            # "stdev": True,
            # "plot": "d"
        }
        qstr = self.querystring(inputdic)
        resp1 = client.get(qstr)
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        assert resp1.status_code == 400
        assert self.error_message(resp1) == self.error_message(resp2)
        assert self.error_message(resp1) == 'gsim: invalid model(s) AkkarEtAl2013'

    @patch('egsim.api.views.PredictionsForm.output', side_effect=ValueError())
    def test_500_err(self, mocked_output_method, client):  # noqa
        with open(self.request_filepath) as _:
            inputdic = dict(yaml.safe_load(_))
        resp1 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        assert resp1.status_code == 500
        assert 'ValueError' in self.error_message(resp1)

    def test_empty_gsim(self,
                        # pytest fixtures:
                        client):
        """tests a special case where a Model has a bug in OpenQuake.
         WARNING: THE BUG MIGHT BE FIXED IN FUTURE OPENQUAKE VERSIONS. As such this test
         could make no sense
        """
        inputdic = {
            "gsim": [
                "AbrahamsonEtAl2014",
                # "AbrahamsonEtAl2014NSHMPLower",
                # "AbrahamsonEtAl2014NSHMPMean",
                # "AbrahamsonEtAl2014NSHMPUpper",
                "AbrahamsonEtAl2014RegCHN",
                "AbrahamsonEtAl2014RegJPN",
                "AbrahamsonEtAl2014RegTWN",
                "AkkarBommer2010SWISS01",
                "AkkarBommer2010SWISS04",
                "AkkarBommer2010SWISS08",
                "AkkarEtAlRepi2014"
            ],
            "imt": ["PGA", "PGV"],
            "magnitude": [3, 4],
            "distance": [10, 11, 12],
            "dip": "60",
            "aspect": "1.5",
            "rake": "0.0",
            "ztor": "0.0",
            "strike": "0.0",
            "msr": "WC1994",
            "initial_point": [0, 0],
            "hypocentre_location": [0.5, 0.5],
            "vs30": "760.0",
            "vs30_measured": True,
            "line_azimuth": "0.0"
        }
        resp1 = client.get(self.querystring(inputdic))
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        # WARNING THIS SHOULD BE A BUG FIXED IN FUTURE OPENQUAKE VERSIONS:
        assert resp1.status_code == 400
        assert 'AkkarBommer2010SWISS01' in self.error_message(resp2)

    def test_mismatching_imt_gsim(self,
                                  # pytest fixtures:
                                  client):
        """tests a model supplied with an invalid imt"""
        imtz = {
            imt_name(i) for i in AkkarEtAlRjb2014.DEFINED_FOR_INTENSITY_MEASURE_TYPES
        }
        undefined_imt = [_ for _ in registered_imts.keys() if _ not in imtz]

        for imtx in undefined_imt:
            inputdic = {
                "gsim": [
                    "AkkarEtAlRjb2014"
                ],
                "imt": [imtx],
                "magnitude": [3, 4],
                "distance": [10, 11, 12],
                "dip": "60",
                "aspect": "1.5",
                "rake": "0.0",
                "ztor": "0.0",
                "strike": "0.0",
                "msr": "WC1994",
                "initial_point": [0, 0],
                "hypocentre_location": [0.5, 0.5],
                "vs30": "760.0",
                "vs30_measured": True,
                "line_azimuth": "0.0",
                # "stdev": True,
                # "plot": "d"
            }
            resp1 = client.get(self.querystring(inputdic))
            resp2 = client.post(self.url, data=inputdic,
                                content_type='application/json')
            assert resp1.status_code == 400
            assert self.error_message(resp1) == self.error_message(resp2)
            assert 'gsim' in self.error_message(resp1) and \
                   'imt' in self.error_message(resp1)

    def test_trellis_error_ngaeast(self,
                                   # pytest fixtures:
                                   client):
        """test trellis distance and distance stdev"""
        with open(self.request_filepath) as _:
            inputdic = dict(yaml.safe_load(_))

        inputdic['magnitude'] = [1, 2, 3]  # outside mag bounds for 1st model below
        inputdic['model'] = [
            "NGAEastUSGSSammons1",
            "NGAEastUSGSSammons10"
        ]
        # and from now on,
        resp1 = client.get(self.querystring(inputdic))
        resp2 = client.post(self.url, data=inputdic,
                            content_type=MimeType.json)
        assert resp1.status_code == resp2.status_code == 400
        err_msg = resp1.content
        assert err_msg == resp2.content
        assert err_msg.startswith(b'NGAEastUSGSSammons1: Magnitude 1.00 outside '
                                  b'of supported range (4.00 to 8.20) (OpenQuake '
                                  b'ValueError @')

        # test a magnitude compatible with the model:
        inputdic['magnitude'] = [4.5]
        resp1 = client.get(self.querystring(inputdic))
        resp2 = client.post(self.url, data=inputdic,
                            content_type=MimeType.json)
        assert resp1.status_code == resp2.status_code == 200

    @patch('egsim.smtk.scenarios.get_ground_motion_values', side_effect=ValueError('a'))
    def test_trellis_model_error(
            self,
            mock_get_gmv,
            # pytest fixtures:
            client):
        """test trellis distance and distance stdev"""
        with open(self.request_filepath) as _:
            inputdic = dict(yaml.safe_load(_))

        # and from now on,
        resp1 = client.get(self.querystring(inputdic))
        resp2 = client.post(self.url, data=inputdic,
                            content_type=MimeType.json)
        assert resp1.status_code == resp2.status_code == 500
        err_msg = resp1.content
        assert err_msg == resp2.content
        assert mock_get_gmv.called
        assert err_msg.startswith(b'Server error (ValueError): a. ')
