"""
Tests the client for the residuals service API

Created on 22 Oct 2018

@author: riccardo
"""
import re

import pytest

from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.datastructures import MultiValueDict

from egsim.api.forms.flatfile.residuals import ResidualsForm
from egsim.api.views import ResidualsView, RESTAPIView


@pytest.mark.django_db
class Test:
    """tests the residuals service"""

    url = "/" + ResidualsView.urls[0]  # '/query/residuals'
    request_filename = 'request_residuals.yaml'

    def querystring(self, data):
        return f'{self.url}?{ResidualsView.formclass(dict(data)).as_querystring()}'

    def test_uploaded_flatfile(self,
                               # pytest fixtures:
                               testdata, areequal, client):
        inputdic = testdata.readyaml(self.request_filename)
        # no flatfile, uploaded flatfile:
        inputdic['plot'] = 'res'
        inputdic2 = dict(inputdic)
        inputdic2.pop('flatfile')
        resp2 = client.post(self.url, data=inputdic2,
                            content_type='application/json')
        resp1 = client.get(self.querystring(inputdic2))
        assert resp1.status_code == resp2.status_code == 400
        assert 'flatfile' in resp1.json()['error']['message']

        # Uploaded flatfile, but not well formed:
        csv = SimpleUploadedFile("file.csv", b"a,b,c,d", content_type="text/csv")
        inputdic2 = dict(inputdic, flatfile=csv, plot='res')
        # test wrong flatfile:
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 400
        assert 'flatfile' in resp2.json()['error']['message']

        def fake_post(self, request):
            # Django testing class `client` expects every data in the `data` argument
            # whereas Django expects two different arguments, `data` and `files`
            # this method simply bypasses the files renaming (from the user provided
            # flatfile into 'uploaded_flatfile' in the Form) and calls directly :
            return ResidualsView().response(data=dict(inputdic2, flatfile='esm2018'),
                                            files=MultiValueDict({'flatfile': csv}))

        with patch.object(RESTAPIView, 'post', fake_post):
            resp2 = client.post(self.url, data=inputdic2)
            assert resp2.status_code == 400
            assert 'flatfile' in resp2.json()['error']['message']

    def test_kotha_turkey(self, client, testdata):
        # Uploaded flatfile, but not well formed:
        csv = SimpleUploadedFile("file.csv",
                                 testdata.read('Turkey_20230206_flatfile_geometric_mean.csv'),
                                 content_type="text/csv")
        inputdic2 = {'model': 'KothaEtAl2020ESHM20', 'imt' : 'PGA',
                     'flatfile':csv, 'plot':'res'}
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 200

    def test_cauzzi_rjb_turkey(self, client, testdata):
        # Uploaded flatfile, but not well formed:
        csv = SimpleUploadedFile("file.csv",
                                 testdata.read('Turkey_20230206_flatfile_geometric_mean.csv'),
                                 content_type="text/csv")
        inputdic2 = {'model': 'CauzziEtAl2014', 'imt' : 'PGA',
                     'flatfile':csv, 'plot':'rjb'}
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 200

    def test_cauzzi_vs30_turkey(self, client, testdata):
        # Uploaded flatfile, but not well formed:
        csv = SimpleUploadedFile("file.csv",
                                 testdata.read('Turkey_20230206_flatfile_geometric_mean.csv'),
                                 content_type="text/csv")
        inputdic2 = {'model': 'CauzziEtAl2014', 'imt' : 'PGA',
                     'flatfile':csv, 'plot':'vs30'}
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 200

    def test_residuals_service_err(self,
                                   # pytest fixtures:
                                   testdata, areequal, client):
        """tests errors in the residuals API service."""
        inputdic = testdata.readyaml(self.request_filename)

        # test conflicting values:
        resp1 = client.get(self.querystring({**inputdic, 'plot': 'res',
                                             'selection-expression': '(vs30 > 800) & (vs30 < 1200)',
                                             'data-query': '(vs30 > 1000) & (vs30 < 1010)'}))
        assert resp1.status_code == 400
        assert 'data-query' in resp1.json()['error']['message']

        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(self.querystring(inputdic))
        assert resp1.status_code == resp2.status_code == 400
        assert areequal(resp1.json(), resp2.json())
        json_ = resp1.json()
        exp_json = {
            'error': {
                'code': 400,
                'message': 'Invalid request. Problems found in: plot. '
                           'See response data for details',
                'errors': [
                    {
                        'location': 'plot',
                        'message': 'This parameter is required',
                        'reason': 'required'
                    }
                ]
            }
        }
        assert areequal(json_, exp_json)

        # Error in plot_type: incalid choice XXX
        inputdic2 = dict(inputdic)
        inputdic2['plot_type'] = 'XXX'
        resp2 = client.post(self.url, data=inputdic2,
                            content_type='application/json')
        resp1 = client.get(self.querystring(inputdic2))
        assert resp1.status_code == resp2.status_code == 400
        assert 'plot_type' in resp1.json()['error']['message']
        assert 'plot_type' in resp2.json()['error']['message']

        # test data query errors:
        inputdic['data-query'] = '(magnitude >5'
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(self.querystring(inputdic))
        assert resp1.status_code == resp2.status_code == 400
        assert 'data-query' in resp1.json()['error']['message']
        assert 'data-query' in resp2.json()['error']['message']

        # test error give in format (text instead of csv):
        inputdict2 = dict(inputdic, format='text')
        inputdict2.pop('data-query')
        resp2 = client.post(self.url, data=inputdict2, content_type='text/csv')
        assert resp2.status_code == 400

    @pytest.mark.parametrize('restype',
                             [_[0] for _ in ResidualsForm.declared_fields['plot_type'].choices])
    def test_residuals_service_(self,
                                restype,
                                # pytest fixtures:
                                testdata, areequal, client):
        """tests the residuals API service."""
        expected_txt = \
            re.compile(b'^imt,residual,model,mean,stddev,median,slope,'
                       b'intercept,pvalue,,*\r\n')
        base_inputdic = testdata.readyaml(self.request_filename)
        # for restype, _ in ResidualsForm.declared_fields['plot_type'].choices:
        inputdic = dict(base_inputdic, plot=restype)
        inputdic['data-query'] = '(vs30 > 1000) & (vs30 < 1010)'
        # sel='(vs30 > 800) & (vs30 < 1200)')
        # selexpr='(vs30 > 1000) & (vs30 < 1010)')
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        assert resp2.status_code == 200
        if restype == 'res':
            # compute the GET request and compare to POST but only for 1
            # residual plot type case, as this test is time consuming:
            resp1 = client.get(self.querystring(inputdic))
            assert resp1.status_code == resp2.status_code
            assert areequal(resp1.json(), resp2.json())

        # FIXME: IMPROVE TESTS? what to assert?

        # test text format:
        resp2 = client.post(self.url, data=dict(inputdic, format='csv'),
                            content_type='text/csv')
        assert resp2.status_code == 200
        assert expected_txt.search(resp2.content)
        assert len(resp2.content) > len(expected_txt.pattern)

    def test_residuals_invalid_get(self,
                                   # pytest fixtures:
                                   testdata, areequal, client):
        """Tests supplying twice the plot_type (invalid) and see what
        happens. This request error can happen only from an API request, not
        from the web portal"""
        resp1 = client.get(self.url +
                           ('?gsim=BindiEtAl2014Rjb&flatfile=wrong_flatfile_name'
                            '&imt=PGA&plot=res&plot=llh'),
                           content_type='application/json')
        # FIXME: the error messages might be made more clear by simply stating:
        # 'only one value possible', but for the moment is ok like this.
        expected_dict = {
            'error': {
                'code': 400,
                'message': 'Invalid request. Problems found in: flatfile, plot. '
                           'See response data for details',
                'errors': [
                    {
                        'location': 'flatfile',
                        'message': 'Value not found or misspelled: wrong_flatfile_name',
                        'reason': 'invalid_choice'
                    },
                    {
                        'location': 'plot',
                        'message': "Value not found or misspelled: ['res', 'llh']",
                        'reason': 'invalid_choice'
                    }
                ]
            }
        }
        assert areequal(expected_dict, resp1.json())
        assert resp1.status_code == 400

    def test_allen2012(self,
                       # pytest fixtures:
                       testdata, areequal, client):
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
            'flatfile': 'esm2018',
            "plot": "mag"
        }
        resp1 = client.get(self.url, data=inputdict,
                           content_type='application/json')
        # expected_json = {
        #     'error': {
        #         'code': 400,
        #         'message': ('Unable to perform the request with the current '
        #                     'parameters (AssertionError)')
        #     }
        # }
        # assert areequal(expected_json, resp1.json())
        # assert resp1.status_code == 400
        assert resp1.status_code == 200
