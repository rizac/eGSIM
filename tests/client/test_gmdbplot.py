'''
Tests the client for the gsims service

Created on 22 Oct 2018

@author: riccardo
'''
import pytest

from egsim.core.utils import querystring, DISTANCE_LABEL
from egsim.models import aval_gsims
from mock import patch


class Test:
    '''tests the gsim service'''

    url = '/query/gmdbplot'
    request_filename = 'request_gmdbplot.yaml'
    gmdb_fname = 'esm_sa_flatfile_2018.csv.hd5'

    @patch('egsim.forms.fields.get_gmdb_path')
    def test_gmbdplot_service(self, mock_gmdb_path, testdata, areequal,  # django_db_setup,
                              client):
        '''tests the gmdbplot API service.'''
        mock_gmdb_path.return_value = testdata.path(self.gmdb_fname)

        inputdic = testdata.readyaml(self.request_filename)
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 200
        assert areequal(resp1.json(), resp2.json())
        json_no_sel = resp1.json()

        # Now provide a filtering:
        selexpr = '(vs30 >= 730) & ((magnitude <=4) | (magnitude>=7))'
        inputdic_sel = dict(inputdic, sel=selexpr)
        resp2 = client.post(self.url, data=inputdic_sel,
                            content_type='application/json')
        resp1 = client.get(querystring(inputdic_sel, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 200
        assert areequal(resp1.json(), resp2.json())
        json_sel = resp1.json()

        # test that the selection worked
        assert len(json_no_sel['x']) > len(json_sel['x'])
        # test that magnitudes are what we expect:
        assert any(_ <= 4 or _ >= 7 for _ in json_sel['y'])

    @patch('egsim.forms.fields.get_gmdb_path')
    def test_gmbdplot_service_dists(self, mock_gmdb_path, testdata, areequal,  # django_db_setup,
                                    client):
        '''tests the gmdbplot API service iterating on all distances'''
        mock_gmdb_path.return_value = testdata.path(self.gmdb_fname)

        for dist in DISTANCE_LABEL.keys():
            inputdic = testdata.readyaml(self.request_filename)
            inputdic['distance_type'] = dist
            resp2 = client.post(self.url, data=inputdic,
                                content_type='application/json')
            resp1 = client.get(querystring(inputdic, baseurl=self.url))
            assert resp1.status_code == resp2.status_code == 200
            assert areequal(resp1.json(), resp2.json())
            json_ = resp1.json()
            assert len(json_['x']) == len(json_['y']) > 0
