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

from egsim.api.forms.model_to_data.residuals import ResidualsForm
from egsim.api.views import ResidualsView, RESTAPIView


@pytest.mark.django_db
class Test:
    """tests the residuals service"""

    url = "/" + ResidualsView.urls[0]  # '/query/residuals'
    request_filename = 'request_residuals.yaml'

    def test_uploaded_flatfile(self,
                               # pytest fixtures:
                               testdata, areequal, client, querystring):
        inputdic = testdata.readyaml(self.request_filename)
        # no flatfile, uploaded flatfile:
        inputdic['plot_type'] = 'res'
        inputdic2 = dict(inputdic)
        inputdic2.pop('flatfile')
        resp2 = client.post(self.url, data=inputdic2,
                            content_type='application/json')
        resp1 = client.get(querystring(inputdic2, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 400
        assert 'flatfile' in resp1.json()['error']['message']

        # both flatfile and uploaded flatfile. In Python, this would be when the
        # user submits a json data with 'flatfile' and additionally a 'flatfile'
        # argument in the posted file. Because the Django testing class `client`
        # does not allow this, we first need to patch the view post method:
        def fake_post(self, request):
            # this method simply bypasses the files renaming (from the user provided
            # flatfile into 'uploaded_flatfile' in the Form) and calls directly :
            mvd = MultiValueDict({'flatfile': request.FILES['uploaded_flatfile']})
            return ResidualsView.response(data=request.POST.copy(),files=mvd)

        with patch.object(RESTAPIView, 'post', fake_post):
            inputdic['plot_type'] = 'res'
            csv = SimpleUploadedFile("file.csv", b"a,b,c,d", content_type="text/csv")
            inputdic2 = dict(inputdic, flatfile='esm2018', uploaded_flatfile=csv)
            resp2 = client.post(self.url, data=inputdic2)
            assert resp2.status_code == 400
            assert 'flatfile' in resp2.json()['error']['message']

    def test_residuals_service_err(self,
                                   # pytest fixtures:
                                   testdata, areequal, client, querystring):
        """tests errors in the residuals API service."""
        inputdic = testdata.readyaml(self.request_filename)

        # test conflicting values:
        resp1 = client.get(querystring(dict(inputdic, plot_type='res',
                                            # sel='(vs30 > 800) & (vs30 < 1200)')
                                            sel='(vs30 > 1000) & (vs30 < 1010)'),
                                       baseurl=self.url))
        assert resp1.status_code == resp1.status_code == 400
        assert 'selexpr/sel' in resp1.json()['error']['message'] or \
               'sel/selexpr' in resp1.json()['error']['message']

        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 400
        assert areequal(resp1.json(), resp2.json())
        json_ = resp1.json()
        ptype_s = 'plot'
        exp_json = {
            'error': {
                'code': 400,
                'message': f'Invalid parameter: {ptype_s}',
                'errors': [
                    {
                        'location': f'{ptype_s}',
                        'message': 'This field is required.',
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
        resp1 = client.get(querystring(inputdic2, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 400
        assert 'plot_type' in resp1.json()['error']['message']
        assert 'plot_type' in resp2.json()['error']['message']

        # test selexpr errors:
        inputdic['selexpr'] = '(magnitude >5'
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 400
        assert 'selexpr' in resp1.json()['error']['message']
        assert 'selexpr' in resp2.json()['error']['message']

        # test error give in format (text instead of csv):
        inputdict2 = dict(inputdic, data_format='text')
        inputdict2.pop('selexpr')
        resp2 = client.post(self.url, data=inputdict2,
                            content_type='text/csv')
        assert resp2.status_code == 400

    @pytest.mark.parametrize('restype',
                             [_[0] for _ in ResidualsForm.declared_fields['plot_type'].choices])
    def test_residuals_service_(self,
                                restype,
                                # pytest fixtures:
                                testdata, areequal, client, querystring):
        """tests the residuals API service."""
        expected_txt = \
            re.compile(b'^imt,type,gsim,mean,stddev,median,slope,'
                       b'intercept,pvalue,,*\r\n')
        base_inputdic = testdata.readyaml(self.request_filename)
        # for restype, _ in ResidualsForm.declared_fields['plot_type'].choices:
        inputdic = dict(base_inputdic, plot_type=restype,
                        # sel='(vs30 > 800) & (vs30 < 1200)')
                        selexpr='(vs30 > 1000) & (vs30 < 1010)')
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        assert resp2.status_code == 200
        if restype == 'res':
            # compute the GET request and compare to POST but only for 1
            # residual plot type case, as this test is time consuming:
            resp1 = client.get(querystring(inputdic, baseurl=self.url))
            assert resp1.status_code == resp2.status_code
            assert areequal(resp1.json(), resp2.json())

        # FIXME: IMPROVE TESTS? what to assert?

        # test text format:
        resp2 = client.post(self.url, data=dict(inputdic, data_format='csv'),
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
                            '&imt=PGA&plot_type=res&plot_type=llh'),
                           content_type='application/json')
        # FIXME: the error messages might be made more clear by simply stating:
        # 'only one value possible', but for the moment is ok like this.
        expected_dict = {
            'error': {
                'code': 400,
                'message': 'Invalid parameters: flatfile, plot_type',
                'errors': [
                    {
                        'location': 'flatfile',
                        'message': 'Select a valid choice. That choice is not '
                                   'one of the available choices.',
                        'reason': 'invalid_choice'
                    },
                    {
                        'location': 'plot_type',
                        'message': ("Select a valid choice. "
                                    "['res', 'llh'] is not one of the "
                                    "available choices."),
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
            "plot_type": "mag"
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
