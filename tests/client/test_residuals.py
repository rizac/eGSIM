'''
Tests the client for the gsims service

Created on 22 Oct 2018

@author: riccardo
'''
import pytest
from mock import patch

from egsim.core.utils import querystring, DISTANCE_LABEL
from egsim.forms.fields import ResidualplottypeField


@pytest.mark.django_db
class Test:
    '''tests the gsim service'''

    url = '/query/residuals'
    request_filename = 'request_residuals.yaml'
    gmdb_fname = 'esm_sa_flatfile_2018.csv.hd5'

    # @patch('egsim.core.utils.get_gmdb_path')
    @patch('egsim.forms.fields.get_gmdb_path')
    def test_residuals_service_err(self, mock_gmdb_path, testdata, areequal,  # django_db_setup,
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

    @patch('egsim.forms.fields.get_gmdb_path')
    def test_residuals_service_(self, mock_gmdb_path, testdata, areequal,  # django_db_setup,
                                client):
        '''tests the gmdbplot API service.'''
        mock_gmdb_path.return_value = testdata.path(self.gmdb_fname)
        print(testdata.path(self.gmdb_fname))
        base_inputdic = testdata.readyaml(self.request_filename)
        for restype in ResidualplottypeField._base_choices:
            inputdic = dict(base_inputdic, plot_type=restype,
                            sel='(vs30 > 800) & (vs30 < 1200)')
            resp2 = client.post(self.url, data=inputdic,
                                content_type='application/json')
            resp1 = client.get(querystring(inputdic, baseurl=self.url))
            assert resp1.status_code == resp2.status_code == 200
            assert areequal(resp1.json(), resp2.json())
            json_ = resp1.json()
            exp_json = "?"
