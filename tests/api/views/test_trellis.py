"""
Tests the client for the trellis service API

Created on 2 Jun 2018

@author: riccardo
"""
from io import BytesIO

import pytest
import numpy as np
from openquake.hazardlib.gsim.akkar_2014 import AkkarEtAlRjb2014

from egsim.api.views import (TrellisView, MIMETYPE, read_hdf_from_buffer,
                             read_csv_from_buffer)
from egsim.api.forms.trellis import TrellisForm

from unittest.mock import patch  # ok in py3.8  # noqa

from egsim.smtk import registered_imts
from egsim.smtk.registry import imt_name


@pytest.mark.django_db
class Test:
    """tests the gsim service"""

    url = "/" + TrellisView.urls[0]  # '/query/trellis'
    request_filename = 'request_trellis.yaml'

    def querystring(self, data):
        return f'{self.url}?{TrellisView.formclass(dict(data)).as_querystring()}'

    # @pytest.mark.parametrize('st_dev', [False, True])
    def test_trellis(
            self,
            # pytest fixtures:
            client, testdata, areequal):
        """test trellis distance and distance stdev"""
        inputdic = dict(testdata.readyaml(self.request_filename))
        resp1 = client.get(self.querystring(inputdic))
        resp2 = client.post(self.url, data=inputdic,
                            content_type=MIMETYPE.JSON)
        result = resp1.json()
        assert resp1.status_code == 200
        assert areequal(result, resp2.json())
        form = TrellisForm(data=dict(inputdic))
        assert form.is_valid()
        input_ = form.cleaned_data
        assert sorted(result.keys()) == ['PGA', 'PGV', 'SA(0.2)', 'mag', 'rrup']
        assert list(result.keys())[1] == 'rrup'
        assert len(result['mag']) == len(result['rrup']) == 12
        result_json = result

        # test the text response:
        resp = client.post(self.url, data=dict(inputdic, format=MIMETYPE.CSV.name),
                            content_type=MIMETYPE.CSV)
        assert resp.status_code == 200
        result_csv = read_csv_from_buffer(BytesIO(b''.join(resp.streaming_content)))

        # test the hdf response:
        resp = client.post(self.url, data=dict(inputdic, format=MIMETYPE.HDF.name),
                            content_type=MIMETYPE.HDF)
        assert resp.status_code == 200
        result_hdf = read_hdf_from_buffer(BytesIO(b''.join(resp.streaming_content)))

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

    def test_ok_request(self,
                        # pytest fixtures:
                        client, areequal):
        """Test some invalid name and a missing IMT FIXME: move to form test?"""
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
            #"stdev": False,
            "strike": 0,
            "vs30": 760,
            "vs30measured": True,
            "z1": None,
            "z2pt5": None,
            "ztor": 0
        }
        resp = client.post(self.url, data=data,
                            content_type='application/json')
        result = resp.json()
        assert resp.status_code == 400

    def test_error(self,
                   # pytest fixtures:
                   client, areequal):
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
        result = resp1.json()
        assert resp1.status_code == 400
        assert areequal(result, resp2.json())

        expected_err_json = {
                # 'code': 400,
            'message': 'Invalid request. Problems found in: gsim',
            'errors': [
                {
                    'location': 'gsim',
                    'message': 'Value not found or misspelled: AkkarEtAl2013',
                    'reason': 'invalid_choice'
                }
            ]
        }
        assert areequal(result, expected_err_json)

    def test_empty_gsim(self,
                        # pytest fixtures:
                        areequal, client):
        """tests a special case whereby a GSIM is empty (this case raised
        before a PR to smtk repository)
        FIXME 2023: OpenQuake =3.15.0 raises again, test this
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
        result = resp1.json()
        assert resp1.status_code == 500
        assert 'AkkarBommer2010SWISS01' in resp2.json()['message']


    def test_mismatching_imt_gsim(self,
                                  # pytest fixtures:
                                  areequal, client):
        """tests a model supplied with an invalid imt"""
        imtz = {imt_name(i) for i in AkkarEtAlRjb2014.DEFINED_FOR_INTENSITY_MEASURE_TYPES}
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
            result = resp1.json()
            assert resp1.status_code == 400
            assert areequal(result, resp2.json())
            assert 'gsim' in resp1.json()['message'] and \
                   'imt' in resp1.json()['message']
