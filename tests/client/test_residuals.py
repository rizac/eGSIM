'''
Tests the client for the residuals service API

Created on 22 Oct 2018

@author: riccardo
'''
import re
import pytest
from mock import patch, PropertyMock

from egsim.core.utils import querystring
from egsim.forms.fields import ResidualplottypeField
from egsim.forms.forms import ResidualsForm


@pytest.mark.django_db
class Test:
    '''tests the residuals service'''

    url = '/query/residuals'
    request_filename = 'request_residuals.yaml'
    gmdb_fname = 'esm_sa_flatfile_2018.csv.hd5'

    @pytest.fixture(autouse=True)
    def setup_gmdb(self,
                   # pytest fixtures:
                   mocked_gmdbfield):
        '''This fixtures mocks the gmdb and it's called before each test
        of this class'''

        class MockedResidualsForm(ResidualsForm):
            '''mocks GmdbPlot'''
            gmdb = mocked_gmdbfield(self.gmdb_fname)

        with patch('egsim.views.ResidualsView.formclass',
                   new_callable=PropertyMock) as mock_gmdb_field:
            mock_gmdb_field.return_value = MockedResidualsForm
            yield

    def test_residuals_service_err(self,
                                   # pytest fixtures:
                                   testdata, areequal, client):
        '''tests errors in the residuals API service.'''
        inputdic = testdata.readyaml(self.request_filename)
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 400
        assert areequal(resp1.json(), resp2.json())
        json_ = resp1.json()
        exp_json = {
            'error': {
                'code': 400,
                'message': 'Invalid input in plot_type',
                'errors': [
                    {
                        'domain': 'plot_type',
                        'message': 'This field is required.',
                        'reason': 'required'
                    }
                ]
            }
        }
        assert areequal(json_, exp_json)

        # FIXME: better test, check more in the errors!

        inputdic = dict(inputdic)
        for ddd in ['dist', 'distance_type']:
            inputdic.pop('dist', None)
        inputdic['plot_type'] = 'dist'
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 400

        # test selexpr errors:
        inputdic = dict(inputdic)
        inputdic['selexpr'] = '(magnitude >5'
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 400

    def test_residuals_service_(self,
                                # pytest fixtures:
                                testdata, areequal, client):
        '''tests the residuals API service.'''
        expected_txt = \
            re.compile(b'^gsim,imt,type,mean,stddev,median,slope,'
                       b'intercept,pvalue,,*\r\n')
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
            # FIXME: IMPROVE TESTS? what to assert?

            # test text format:
            resp2 = client.post(self.url, data=dict(inputdic, format='text'),
                                content_type='text/csv')
            assert resp2.status_code == 200
            assert expected_txt.search(resp2.content)
            assert len(resp2.content) > len(expected_txt.pattern)

