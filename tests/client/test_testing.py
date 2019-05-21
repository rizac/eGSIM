'''
Tests the client for the testing service API

Created on 22 Oct 2018

@author: riccardo
'''
import pytest
from mock import patch, PropertyMock

from egsim.core.utils import querystring
from egsim.forms.forms import TestingForm


@pytest.mark.django_db
class Test:
    '''tests the gsim service'''

    url = '/query/testing'
    request_filename = 'request_testing.yaml'
    gmdb_fname = 'esm_sa_flatfile_2018.csv.hd5'

    @pytest.fixture(autouse=True)
    def setup_gmdb(self,
                   # pytest fixtures:
                   mocked_gmdbfield):
        '''This fixtures mocks the gmdb and it's called before each test
        of this class'''
        class MockedTestingForm(TestingForm):
            '''mocks GmdbPlot'''
            gmdb = mocked_gmdbfield(self.gmdb_fname)

        with patch('egsim.views.TestingView.formclass',
                   new_callable=PropertyMock) as mock_gmdb_field:
            mock_gmdb_field.return_value = MockedTestingForm
            yield

    def test_residuals_service_err(self,
                                   # pytest fixtures:
                                   testdata, areequal, client):
        '''tests errors in the testing API service.'''
        inputdic = testdata.readyaml(self.request_filename)
        inputdic.pop('fit_measure')
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 400
        assert areequal(resp1.json(), resp2.json())
        json_ = resp1.json()
        exp_json = {
            'error': {
                'code': 400,
                'message': 'Invalid input in fit_measure',
                'errors': [
                    {
                        'domain': 'fit_measure',
                        'message': 'This field is required.',
                        'reason': 'required'
                    }
                ]
            }
        }
        assert areequal(json_, exp_json)

    def test_testing_service(self,
                             # pytest fixtures:
                             testdata, areequal, client):
        '''tests the gmdbplot API service.'''
        inputdic = testdata.readyaml(self.request_filename)
        # pass two gsims that have records with the current test gmdb:
        inputdic['gsim'] = ['Atkinson2015', 'BindiEtAl2014RhypEC8NoSOF']
        inputdic['selexpr'] = ''
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 200
        assert areequal(resp1.json(), resp2.json())
        json_ = resp1.json()
        assert isinstance(json_, dict) and \
            all(isinstance(_, dict) for _ in json_.values())

        # test text format:
        resp2 = client.post(self.url, data=dict(inputdic, format='text'),
                            content_type='text/csv')
        assert resp2.status_code == 200
        exp_str = b'measure of fit,imt,gsim,db records,value\r\n'
        assert resp2.content.startswith(exp_str)
        assert len(resp2.content) > len(exp_str)

    def test_testing_service_zero_records(self,
                                          # pytest fixtures:
                                          testdata, areequal, client):
        '''tests the gmdbplot API service.'''
        inputdic = testdata.readyaml(self.request_filename)
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 200
        assert areequal(resp1.json(), resp2.json())
        json_ = resp1.json()
        assert isinstance(json_, dict) and \
            all(isinstance(_, dict) for _ in json_.values())

        # test text format:
        resp2 = client.post(self.url, data=dict(inputdic, format='text'),
                            content_type='text/csv')
        assert resp2.status_code == 200
        assert resp2.content == b'measure of fit,imt,gsim,db records,value\r\n'
        # test with no selexpr. Unfortunately, no matching db rows
        # found. FIXME: try with some other gsim?
        resp2 = client.post(self.url, data=dict(inputdic, format='text',
                                                selexpr=''),
                            content_type='text/csv')
        assert resp2.status_code == 200
        assert resp2.content == b'measure of fit,imt,gsim,db records,value\r\n'
