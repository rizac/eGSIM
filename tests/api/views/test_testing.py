"""
Tests the client for the testing service API

Created on 22 Oct 2018

@author: riccardo
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from egsim.api.views import TestingView


@pytest.mark.django_db
class Test:
    """tests the testing service"""

    url = "/" + TestingView.urls[0]  # '/query/residuals'
    request_filename = 'request_testing.yaml'

    def querystring(self, data):
        return f'{self.url}?{TestingView.formclass(dict(data)).as_querystring()}'

    def test_residuals_service_err(self,
                                   # pytest fixtures:
                                   testdata, areequal, client):
        """test errors in the testing API service."""
        inputdic = testdata.readyaml(self.request_filename)
        inputdic.pop('mof')
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(self.querystring(inputdic))
        assert resp1.status_code == resp2.status_code == 400
        assert areequal(resp1.json(), resp2.json())
        json_ = resp1.json()
        exp_json = {
            'error': {
                'code': 400,
                'message': 'Invalid request. Problems found in: fit-measure. '
                           'See response data for details',
                'errors': [
                    {
                        'location': 'fit-measure',
                        'message': 'This parameter is required',
                        'reason': 'required'
                    }
                ]
            }
        }
        assert areequal(json_, exp_json)

    def test_kotha_turkey(self, client, testdata):
        # Uploaded flatfile, but not well formed:
        csv = SimpleUploadedFile("file.csv",
                                 testdata.read(
                                     'Turkey_20230206_flatfile_geometric_mean.csv'),
                                 content_type="text/csv")
        inputdic2 = {'model': 'KothaEtAl2020ESHM20', 'imt': 'PGA',
                     'flatfile': csv, 'fit-measure': ['res', 'l']}
        # test wrong flatfile:
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 200


    def test_testing_service(self,
                             # pytest fixtures:
                             testdata, areequal, client):
        """tests the "testing" API service."""
        inputdic = testdata.readyaml(self.request_filename)
        # pass two gsims that have records with the current test gmdb:
        # inputdic['gsim'] = ['Atkinson2015', 'BindiEtAl2014RhypEC8NoSOF']
        # inputdic['selexpr'] = ''
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(self.querystring(inputdic))
        assert resp1.status_code == resp2.status_code == 200
        assert areequal(resp1.json(), resp2.json())
        json_ = resp1.json()
        assert isinstance(json_, dict) and \
            all(isinstance(_, dict) for _ in json_.values())

        # test text format:
        resp2 = client.post(self.url, data=dict(inputdic, format='csv'),
                            content_type='text/csv')
        assert resp2.status_code == 200
        exp_str = b'measure of fit,imt,model,value,db records used\r\n'
        assert resp2.content.startswith(exp_str)
        assert len(resp2.content) > len(exp_str)

    def test_testing_service_zero_records(self,
                                          # pytest fixtures:
                                          testdata, areequal, client):
        """tests the "testing" API service."""
        inputdic = testdata.readyaml(self.request_filename)
        inputdic['data-query'] = 'magnitude>10'
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(self.querystring(inputdic))
        assert resp1.status_code == resp2.status_code == 200
        assert areequal(resp1.json(), resp2.json())
        json_ = resp1.json()
        assert isinstance(json_, dict) and \
            all(isinstance(_, dict) for _ in json_.values())

        # test text format:
        resp2 = client.post(self.url, data=dict(inputdic, format='csv'),
                            content_type='text/csv')
        assert resp2.status_code == 200
        assert resp2.content == (b'measure of fit,imt,model,value,'
                                 b'db records used\r\n')

    def test_tesing_bug(self,
                        # pytest fixtures:
                        testdata, areequal, client):
        """Tests an old bug that should have been fixed"""
        # FIXME: this was a 1.0 version bug. Does it make sense to keep the test?
        resp1 = client.get(self.url +
                           '?flatfile=esm2018&gsim=BindiEtAl2014Rjb&imt=PGA&fit-measure=res',
                           content_type='application/json')
        assert resp1.status_code == 200
