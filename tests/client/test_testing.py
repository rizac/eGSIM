"""
Tests the client for the testing service API

Created on 22 Oct 2018

@author: riccardo
"""
import pytest

from egsim.api.views import TestingView


@pytest.mark.django_db
class Test:
    """tests the testing service"""

    url = "/" + TestingView.urls[0]  # '/query/residuals'
    request_filename = 'request_testing.yaml'

    def test_residuals_service_err(self,
                                   # pytest fixtures:
                                   testdata, areequal, client, querystring):
        """test errors in the testing API service."""
        inputdic = testdata.readyaml(self.request_filename)
        inputdic.pop('mof')
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 400
        assert areequal(resp1.json(), resp2.json())
        json_ = resp1.json()
        exp_json = {
            'error': {
                'code': 400,
                'message': 'Invalid parameter: mof',
                'errors': [
                    {
                        'location': 'mof',
                        'message': 'This field is required.',
                        'reason': 'required'
                    }
                ]
            }
        }
        assert areequal(json_, exp_json)

    def test_testing_service(self,
                             # pytest fixtures:
                             testdata, areequal, client, querystring):
        """tests the "testing" API service."""
        inputdic = testdata.readyaml(self.request_filename)
        # pass two gsims that have records with the current test gmdb:
        # inputdic['gsim'] = ['Atkinson2015', 'BindiEtAl2014RhypEC8NoSOF']
        # inputdic['selexpr'] = ''
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 200
        assert areequal(resp1.json(), resp2.json())
        json_ = resp1.json()
        assert isinstance(json_, dict) and \
            all(isinstance(_, dict) for _ in json_.values())

        # test text format:
        resp2 = client.post(self.url, data=dict(inputdic, format='csv'),
                            content_type='text/csv')
        assert resp2.status_code == 200
        exp_str = b'measure of fit,imt,gsim,value,db records used\r\n'
        assert resp2.content.startswith(exp_str)
        assert len(resp2.content) > len(exp_str)

    def test_testing_service_zero_records(self,
                                          # pytest fixtures:
                                          testdata, areequal, client, querystring):
        """tests the "testing" API service."""
        inputdic = testdata.readyaml(self.request_filename)
        inputdic['selexpr'] = 'magnitude>10'
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 200
        assert areequal(resp1.json(), resp2.json())
        json_ = resp1.json()
        assert isinstance(json_, dict) and \
            all(isinstance(_, dict) for _ in json_.values())

        # test text format:
        resp2 = client.post(self.url, data=dict(inputdic, format='csv'),
                            content_type='text/csv')
        assert resp2.status_code == 200
        assert resp2.content == (b'measure of fit,imt,gsim,value,'
                                 b'db records used\r\n')

    def test_tesing_bug(self,
                        # pytest fixtures:
                        testdata, areequal, client):
        """Tests a bug we spotted by testing the API from an external query
        that should be fixed"""
        # FIXME: this was a 1.0 version bug. Does it make sense to keep the test?
        resp1 = client.get(self.url +
                           '?flatfile=esm2018&gsim=BindiEtAl2014Rjb&imt=PGA&fit_measure=res',
                           content_type='application/json')
        assert resp1.status_code == 200
