"""
Tests the client for the residuals service API

Created on 22 Oct 2018

@author: riccardo
"""
import pytest

from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.datastructures import MultiValueDict

from egsim.api.views import ResidualsView, RESTAPIView, as_querystring, MIMETYPE, \
    read_csv_from_buffer, read_hdf_from_buffer
from egsim.smtk.converters import dataframe2dict


@pytest.mark.django_db
class Test:
    """tests the residuals service"""

    url = "/" + ResidualsView.urls[0]  # '/query/residuals'
    request_filename = 'request_residuals.yaml'

    def querystring(self, data):
        return f'{self.url}?{as_querystring(data)}'

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
        assert 'flatfile' in resp1.json()['message']

        # Uploaded flatfile, but not well formed:
        csv = SimpleUploadedFile("file.csv", b"a,b,c,d", content_type="text/csv")
        inputdic2 = dict(inputdic, flatfile=csv, plot='res')
        # test wrong flatfile:
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 400
        assert 'flatfile' in resp2.json()['message']

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
            assert 'flatfile' in resp2.json()['message']

    def test_kotha_turkey(self, client, testdata):
        csv = SimpleUploadedFile("file.csv",
                                 testdata.read('tk_20230206_flatfile_geometric_mean.csv'),
                                 content_type="text/csv")
        inputdic2 = {
            'model': 'KothaEtAl2020ESHM20',
            'imt' : 'PGA',
            'flatfile':csv
        }
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 200

    def test_cauzzi_rjb_turkey(self, client, testdata):
        csv = SimpleUploadedFile("file.csv",
                                 testdata.read('tk_20230206_flatfile_geometric_mean.csv'),
                                 content_type="text/csv")
        inputdic2 = {
            'model': 'CauzziEtAl2014',
            'imt' : 'PGA',
            'flatfile':csv
        }
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 200

    def test_cauzzi_vs30_turkey(self, client, testdata):
        csv = SimpleUploadedFile("file.csv",
                                 testdata.read('tk_20230206_flatfile_geometric_mean.csv'),
                                 content_type="text/csv")
        inputdic2 = {
            'model': 'CauzziEtAl2014',
            'imt' : 'PGA',
            'flatfile':csv,
        }
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 200

    def test_bindi17_turkey(self, client, testdata):
        # Uploaded flatfile, but not well-formed:
        csv = SimpleUploadedFile("file.csv",
                                 testdata.read('PGA_BindiEtAl17.csv'),
                                 content_type="text/csv")
        inputdic2 = {
            'model': 'BindiEtAl2017Rhypo',
            'imt' : 'PGA',
            'flatfile':csv
        }
        resp2 = client.post(self.url, data=inputdic2)
        assert resp2.status_code == 200
        resp_json = resp2.json()
        assert "PGA" in resp_json

    def test_residuals_service_err(self,
                                   # pytest fixtures:
                                   testdata, areequal, client):
        """tests errors in the residuals API service."""
        inputdic = testdata.readyaml(self.request_filename)

        # test conflicting values:
        resp1 = client.get(self.querystring({**inputdic,
                                             'selection-expression': '(vs30 > 800) & (vs30 < 1200)',
                                             'data-query': '(vs30 > 1000) & (vs30 < 1010)'}))
        assert resp1.status_code == 400
        assert 'data-query' in resp1.json()['message']

        inputdic['data-query'] = '(magnitude >5'
        resp2 = client.post(self.url, data=inputdic, content_type='application/json')
        resp1 = client.get(self.querystring(inputdic))
        assert resp1.status_code == resp2.status_code == 400
        err_msg = resp1.json()['message']
        assert 'data-query' in err_msg
        assert 'data-query' in err_msg

        # test error give in format (text instead of csv):
        inputdict2 = dict(inputdic, format='text')
        inputdict2.pop('data-query')
        resp2 = client.post(self.url, data=inputdict2, content_type='text/csv')
        assert resp2.status_code == 400

    def test_residuals_service(self,
                                   # pytest fixtures:
                                   testdata, areequal, client):
        inputdic = testdata.readyaml(self.request_filename)
        inputdic['data-query'] = '(vs30 >= 1000) & (mag>=7)'

        # resp2 = client.post(self.url, data=inputdic,
        #                     content_type='application/json')
        resp1 = client.get(self.querystring(inputdic))
        assert resp1.status_code == 200
        # resp2.status_code == 200
        # assert areequal(resp1.json(), resp2.json())

        # dfr1 = pd.DataFrame(resp1.json())

        for format in [None, 'csv', 'hdf']:
            if format is None:
                inputdic.pop('format', None)
            else:
                inputdic['format'] = format

        resp2 = client.post(self.url, data=inputdic, content_type=MIMETYPE[format.upper()])
        assert resp2.status_code == 200
        content = resp2.streaming_content
        dfr2 = read_csv_from_buffer(content) if format == 'csv' \
            else read_hdf_from_buffer(content)
        areequal(resp1.json(), dataframe2dict(dfr2))

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
            'flatfile': 'esm2018'
        }
        resp1 = client.get(self.url, data=inputdict,
                           content_type='application/json')
        assert resp1.status_code == 200
