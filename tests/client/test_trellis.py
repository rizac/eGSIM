'''
Tests the client for the trellis service API

Created on 2 Jun 2018

@author: riccardo
'''
import re
import pytest

from egsim.core.utils import querystring
from egsim.forms.forms import TrellisForm
from egsim.core.smtk import _default_periods_for_spectra
from re import search
from mock import patch
from egsim.forms.fields import TextSepField


@pytest.mark.django_db
class Test:
    '''tests the gsim service'''

    url = '/query/trellis'
    request_filename = 'request_trellis.yaml'

    GSIM, IMT = 'gsim', 'imt'

    @pytest.mark.parametrize('trellis_type', ['d', 'ds'])
    def test_trellis_dist(self, client, testdata, areequal, trellis_type):
        '''test trellis distance and distance stdev'''
        inputdic = dict(testdata.readyaml(self.request_filename),
                        plot_type=trellis_type)
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        result = resp1.json()
        assert resp1.status_code == 200
        assert areequal(result, resp2.json())
        form = TrellisForm(data=inputdic)
        assert form.is_valid()
        input_ = form.cleaned_data
        assert sorted(result.keys()) == ['figures', 'xlabel', 'xvalues']
        xvalues = result['xvalues']
        assert len(xvalues) == len(input_['distance']) + 1  # FIXME: should be len(distance)!!!
        figures = result['figures']
        assert len(figures) == len(input_['magnitude']) * len(input_['imt'])
        for fig in figures:
            yvalues = fig['yvalues']
            assert all(len(yval) == len(xvalues) for yval in yvalues.values())
            assert sorted(yvalues.keys()) == sorted(input_['gsim'])

        # test the text response:
        resp2 = client.post(self.url, data=dict(inputdic, format='text'),
                            content_type='text/csv')
        assert resp2.status_code == 200
        assert re.search(b'^gsim,magnitude,distance,vs30(,+)\r\n,,,,',
                         resp2.content)
    
    @pytest.mark.parametrize('trellis_type', ['m', 'ms'])
    def test_trellis_mag(self, client, testdata, areequal, trellis_type):
        '''test trellis magnitude and magnitude stdev'''
        inputdic = dict(testdata.readyaml(self.request_filename),
                        plot_type=trellis_type)
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        result = resp1.json()
        assert resp1.status_code == 200
        assert areequal(result, resp2.json())
        form = TrellisForm(data=inputdic)
        assert form.is_valid()
        input_ = form.cleaned_data
        assert sorted(result.keys()) == ['figures', 'xlabel', 'xvalues']
        xvalues = result['xvalues']
        assert len(xvalues) == len(input_['magnitude'])
        figures = result['figures']
        assert len(figures) == len(input_['distance']) * len(input_['imt'])
        for fig in figures:
            yvalues = fig['yvalues']
            assert all(len(yval) == len(xvalues) for yval in yvalues.values())
            assert sorted(yvalues.keys()) == sorted(input_['gsim'])

        # test the text response:
        resp2 = client.post(self.url, data=dict(inputdic, format='text'),
                            content_type='text/csv')
        assert resp2.status_code == 200
        assert re.search(b'^gsim,magnitude,distance,vs30(,+)\r\n,,,,',
                         resp2.content)
        ref_resp = resp2.content
        # test different text formats
        for text_sep, symbol in TextSepField._base_choices.items():
            resp3 = client.post(self.url, data=dict(inputdic, format='text',
                                                    text_sep=text_sep),
                                content_type='text/csv')
            assert resp3.status_code == 200
            real_content = sorted(_ for _ in resp3.content.split(b'\r\n'))
            expected_content = \
                sorted(_ for _ in \
                       ref_resp.replace(b',',
                                        symbol.encode('utf8')).split(b'\r\n'))
            if text_sep != 'space':
                assert real_content == expected_content

    @pytest.mark.parametrize('trellis_type', ['s', 'ss'])
    def test_trellis_spec(self, client, testdata, areequal, trellis_type):
        '''test trellis magnitude-distance spectra and magnitude-distance
        stdev'''
        inputdic = dict(testdata.readyaml(self.request_filename),
                        plot_type=trellis_type)
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        result = resp1.json()
        assert resp1.status_code == 200
        assert areequal(result, resp2.json())
        form = TrellisForm(data=inputdic)
        assert form.is_valid()
        input_ = form.cleaned_data
        assert sorted(result.keys()) == ['figures', 'xlabel', 'xvalues']
        xvalues = result['xvalues']
        assert len(xvalues) == len(_default_periods_for_spectra())
        figures = result['figures']
        assert len(figures) == len(input_['distance']) * len(input_['magnitude'])
        for fig in figures:
            yvalues = fig['yvalues']
            assert all(len(yval) == len(xvalues) for yval in yvalues.values())
            assert sorted(yvalues.keys()) == sorted(input_['gsim'])

        # test the text response:
        resp2 = client.post(self.url, data=dict(inputdic, format='text'),
                            content_type='text/csv')
        assert resp2.status_code == 200
        assert re.search(b'^gsim,magnitude,distance,vs30(,+)\r\n,,,,',
                         resp2.content)

    def test_error(self, client, areequal):
        '''tests a special case where we supply a deprecated gsim (not in
        EGSIM list)'''
        inputdic = {
            "gsim": ["AkkarEtAl2013", "AkkarEtAlRepi2014"],
            "imt": ["PGA", "PGV"],
            "magnitude": "3:4",
            "distance": "10:12",
            "dip": "60",
            "aspect": "1.5",
            "rake": "0.0",
            "ztor": "0.0",
            "strike": "0.0",
            "msr": "WC1994",
            "initial_point": "0 0",
            "hypocentre_location": "0.5 0.5",
            "vs30": "760.0",
            "vs30_measured": True,
            "line_azimuth": "0.0",
            "plot_type": "ds"
        }

        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        result = resp1.json()
        assert resp1.status_code == 400
        assert areequal(result, resp2.json())

        expected_err_json = {
            'error': {
                'code': 400,
                'message': 'Invalid input in gsim',
                'errors': [
                    {
                        'domain': 'gsim',
                        'message': ('Select a valid choice. AkkarEtAl2013 is '
                                    'not one of the available choices.'),
                        'reason': 'invalid_choice'
                    }
                ]
            }
        }
        assert areequal(result, expected_err_json)

    def test_empty_gsim(self, areequal, client):
        '''tests a special case whereby a GSIM is empty (this case raised
        before a PR to smtk repository)'''
        inputdic = {
            "gsim": [
                "AbrahamsonEtAl2014",
                "AbrahamsonEtAl2014NSHMPLower",
                "AbrahamsonEtAl2014NSHMPMean",
                "AbrahamsonEtAl2014NSHMPUpper",
                "AbrahamsonEtAl2014RegCHN",
                "AbrahamsonEtAl2014RegJPN",
                "AbrahamsonEtAl2014RegTWN",
                "AkkarBommer2010SWISS01",
                "AkkarBommer2010SWISS04",
                "AkkarBommer2010SWISS08",
                "AkkarEtAlRepi2014"
            ],
            "imt": ["PGA", "PGV"],
            "magnitude": "3:4",
            "distance": "10:12",
            "dip": "60",
            "aspect": "1.5",
            "rake": "0.0",
            "ztor": "0.0",
            "strike": "0.0",
            "msr": "WC1994",
            "initial_point": "0 0",
            "hypocentre_location": "0.5 0.5",
            "vs30": "760.0",
            "vs30_measured": True,
            "line_azimuth": "0.0",
            "plot_type": "ds"
        }
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        result = resp1.json()
        assert resp1.status_code == 200
        assert areequal(result, resp2.json())
#         form = TrellisForm(in)
#         assert form.is_valid()
#         result = get_trellis(form.cleaned_data)
        figures = result['figures']
        assert figures[1]['yvalues']['AkkarBommer2010SWISS01'] == []


    def test_mismatching_imt_gsim(self, areequal, client):
        '''tests a special case whereby a GSIM is empty (this case raised
        before a PR to smtk repository)'''
        inputdic = {
            "gsim": [
                "AkkarEtAlRjb2014"
            ],
            "imt": ["CAV"],
            "magnitude": "3:4",
            "distance": "10:12",
            "dip": "60",
            "aspect": "1.5",
            "rake": "0.0",
            "ztor": "0.0",
            "strike": "0.0",
            "msr": "WC1994",
            "initial_point": "0 0",
            "hypocentre_location": "0.5 0.5",
            "vs30": "760.0",
            "vs30_measured": True,
            "line_azimuth": "0.0",
            "plot_type": "ds"
        }
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        result = resp1.json()
        assert resp1.status_code == 400
        assert areequal(result, resp2.json())
        expected_json = {
            'error': {
                'code': 400,
                'message': 'Invalid input in gsim, imt',
                'errors': [
                    {
                        'domain': 'gsim',
                        'message': ('1 gsim(s) not defined for '
                                    'all supplied imt(s)'),
                        'reason': 'invalid'
                    },
                    {
                        'domain': 'imt',
                        'message': ('1 imt(s) not defined for all '
                                    'supplied gsim(s)'),
                        'reason': 'invalid'
                    }
                ]
            }
        }
        assert areequal(resp1.json(), expected_json)

    @patch('egsim.views.TrellisView.to_rows')
    def test_notimplemented_text_format(self, mock_trellis_to_rows,
                                        # pytest fixtures:
                                        testdata, client, areequal):
        '''tests the not implemented error'''
        def seff(*a, **v):
            raise NotImplementedError()
        mock_trellis_to_rows.side_effect = seff
        inputdic = dict(testdata.readyaml(self.request_filename),
                        plot_type='m')
        # test the text response:
        resp2 = client.post(self.url, data=dict(inputdic, format='text'),
                            content_type='text/csv')
        assert resp2.status_code == 400
        expected_json = {
            "error": {
                "code": 400,
                "message": "format \"text\" is not currently implemented"
            }
        }
        assert areequal(resp2.json(), expected_json)
