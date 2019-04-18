'''
Tests the client for the gsims service

Created on 22 Oct 2018

@author: riccardo
'''
import pytest
from mock import patch

from egsim.core.utils import querystring


@pytest.mark.django_db
class Test:
    '''tests the gsim service'''

    url = '/query/testing'
    request_filename = 'request_testing.yaml'
    gmdb_fname = 'esm_sa_flatfile_2018.csv.hd5'

    # @patch('egsim.core.utils.get_gmdb_path')
    @patch('egsim.forms.fields.get_gmdb_path')
    def tst_residuals_service_err(self, mock_gmdb_path, testdata, areequal,  # django_db_setup,
                                  client):
        '''tests the gmdbplot API service.'''
        mock_gmdb_path.return_value = testdata.path(self.gmdb_fname)
        print(testdata.path(self.gmdb_fname))
        inputdic = testdata.readyaml(self.request_filename)
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 400
        assert areequal(resp1.json(), resp2.json())
        json_ = resp1.json()
        exp_json = {'error': {'code': 400,
                              'message': 'Input validation error in plot_type',
                              'errors': [{'domain': 'plot_type',
                                          'message': 'This field is required.',
                                          'reason': 'required'}]}}

        assert areequal(json_, exp_json)

        inputdic = dict(inputdic)
        for ddd in ['dist', 'distance_type']:
            inputdic.pop('dist', None)
        inputdic['plot_type'] = 'dist'
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 400
        

    @patch('egsim.forms.fields.get_gmdb_path')
    def test_testing_service(self, mock_gmdb_path, testdata, areequal,  # django_db_setup,
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
        json_ = resp1.json()
        assert isinstance(json_, dict) and \
            all(isinstance(_, dict) for _ in json_.values())
        
        
