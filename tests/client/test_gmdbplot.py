'''
Tests the client for the gmdbplot service API (as of June 2019, not publicly
exposed)

Created on 22 Oct 2018

@author: riccardo
'''
import pytest
from mock import patch, PropertyMock

from egsim.core.utils import querystring, DISTANCE_LABEL
from egsim.forms.forms import GmdbPlotForm
# from egsim.forms.fields import GmdbField


class Test:
    '''tests the gmdbplot service'''

    url = '/query/gmdbplot'
    request_filename = 'request_gmdbplot.yaml'
    gmdb_fname = 'esm_sa_flatfile_2018.csv.hd5'

    @pytest.fixture(autouse=True)
    def setup_gmdb(self,
                   # pytest fixtures:
                   mocked_gmdbfield):
        '''This fixtures mocks the gmdb and it's called before each test
        of this class'''

        class MockedGmdbplotForm(GmdbPlotForm):
            '''mocks GmdbPlotForm'''
            gmdb = mocked_gmdbfield(self.gmdb_fname)

        with patch('egsim.views.GmdbPlotView.formclass',
                   new_callable=PropertyMock) as mock_gmdb_field:
            mock_gmdb_field.return_value = MockedGmdbplotForm
            yield

    def test_gmbdplot_service(self,
                              # pytest fixtures:
                              testdata, areequal, client):
        '''tests the gmdbplot API service.'''
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

    def test_gmbdplot_service_dists(self,
                                    # pytest fixtures:
                                    testdata, areequal, client):
        '''tests the gmdbplot API service iterating on all distances'''
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

    def test_gmbdplot_errors(self,
                             # pytest fixtures:
                             testdata, areequal, client):
        '''tests the gmdbplot API service with errors'''

        inputdic = testdata.readyaml(self.request_filename)
        inputdic['gmdb'] = 'notexistingtable'
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 400
        assert areequal(resp1.json(), resp2.json())
        json_ = resp1.json()
        expected_json = {
            'error': {
                'code': 400,
                'message': 'Invalid input in gmdb',
                'errors': [
                    {
                        'domain': 'gmdb',
                        'message': ('Select a valid choice. notexistingtable '
                                    'is not one of the available choices.'),
                        'reason': 'invalid_choice'
                    }
                ]
            }
        }
        assert areequal(json_, expected_json)

        inputdic = testdata.readyaml(self.request_filename)
        inputdic['dist'] = 'notexistingdist'
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 400
        assert areequal(resp1.json(), resp2.json())
        json_ = resp1.json()
        expected_json = {
            'error': {
                'code': 400,
                'message': 'Invalid input in distance_type',
                'errors': [
                    {
                        'domain': 'distance_type',
                        'message': ('Select a valid choice. notexistingdist '
                                    'is not one of the available choices.'),
                        'reason': 'invalid_choice'
                    }
                ]
            }
        }
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
        expected = {
            'error': {
                'code': 400,
                'message': 'Invalid input in selexpr',
                'errors': [
                    {
                        'domain': 'selexpr',
                        'message': ('unexpected EOF while parsing: '
                                    '"(magnitude > 5a"'),
                        'reason': 'invalid'
                    }
                ]
            }
        }
        assert areequal(json_, expected)
