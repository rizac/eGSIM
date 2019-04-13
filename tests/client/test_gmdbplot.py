'''
Tests the client for the gsims service

Created on 22 Oct 2018

@author: riccardo
'''
import pytest
from mock import patch

from egsim.core.utils import querystring, DISTANCE_LABEL


class Test:
    '''tests the gsim service'''

    url = '/query/gmdbplot'
    request_filename = 'request_gmdbplot.yaml'
    gmdb_fname = 'esm_sa_flatfile_2018.csv.hd5'

    # @patch('egsim.core.utils.get_gmdb_path')
    @patch('egsim.forms.fields.get_gmdb_path')
    def test_gmbdplot_service(self, mock_gmdb_path, testdata, areequal,  # django_db_setup,
                              client):
        '''tests the gmdbplot API service.'''
        mock_gmdb_path.return_value = testdata.path(self.gmdb_fname)
        print(testdata.path(self.gmdb_fname))
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

    # @patch('egsim.core.utils.get_gmdb_path')
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

    # @patch('egsim.core.utils.get_gmdb_path')
    @patch('egsim.forms.fields.get_gmdb_path')
    def test_gmbdplot_errors(self, mock_gmdb_path, 
                             testdata, areequal,  # django_db_setup,
                             client):
        '''tests the gmdbplot API service with errors'''
        mock_gmdb_path.return_value = testdata.path(self.gmdb_fname)
        # mock_gmdb_path2.return_value = testdata.path(self.gmdb_fname)

        inputdic = testdata.readyaml(self.request_filename)
        inputdic['gmdb'] = 'notexistingtable'
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 400
        assert areequal(resp1.json(), resp2.json())
        json_ = resp1.json()
        expected_json = {'error': {'code': 400,
                                   'message': 'Input validation error in gmdb',
                                   'errors': [{'domain': 'gmdb', 'message':
                                               ('Select a valid '
                                                'choice. notexistingtable is '
                                                'not one of the available '
                                                'choices.'),
                                               'reason': 'invalid_choice'}]}}
        assert areequal(json_, expected_json)

        inputdic = testdata.readyaml(self.request_filename)
        inputdic['dist'] = 'notexistingdist'
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 400
        assert areequal(resp1.json(), resp2.json())
        json_ = resp1.json()
        expected_json = {'error': {'code': 400, 'message':
                                   'Input validation error in distance_type',
                                   'errors': [{'domain': 'distance_type',
                                               'message': ('Select a valid '
                                                           'choice. '
                                                           'notexistingdist '
                                                           'is not one of the '
                                                           'available '
                                                           'choices.'),
                                               'reason': 'invalid_choice'}]}}
        assert areequal(json_, expected_json)

        inputdic = testdata.readyaml(self.request_filename)
        inputdic['sel'] = '(magnitude > 5a'  # expression error
        # this should be caught by the middleware. For the moment
        # we assert it raises:
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 400
        assert areequal(resp1.json(), resp2.json())
        json_ = resp1.json()
        expected = {'error': {'code': 400, 'message': ('Selection expression '
                                                       'error: "(magnitude > '
                                                       '5a"')}}
        assert areequal(json_, expected)
