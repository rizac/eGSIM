'''
Created on 2 Jun 2018

@author: riccardo
'''
import pytest

from egsim.core.utils import querystring
from egsim.forms.forms import TrellisForm
from egsim.core.smtk import _default_periods_for_spectra


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
    
    def test_error(self, client, areequal):
        '''tests a special case where we supply a deprecated gsim (not in
        EGSIM list)'''
        inputdic = {"gsim": ["AkkarEtAl2013", "AkkarEtAlRepi2014"],
                    "imt": ["PGA", "PGV"], "magnitude": "3:4",
                    "distance": "10:12", "dip": "60",
                    "aspect": "1.5", "rake": "0.0", "ztor": "0.0",
                    "strike": "0.0", "msr": "WC1994",
                    "initial_point": "0 0", "hypocentre_location": "0.5 0.5",
                    "vs30": "760.0", "vs30_measured": True,
                    "line_azimuth": "0.0", "plot_type": "ds"}

        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        result = resp1.json()
        assert resp1.status_code == 400
        assert areequal(result, resp2.json())

        expected_err_json = \
            {'error': {'code': 400,
                       'message': 'Input validation error in gsim',
                       'errors': [{'domain': 'gsim',
                                   'message': ('Select a valid choice. '
                                               'AkkarEtAl2013 is not one of '
                                               'the available choices.'),
                                   'reason': 'invalid_choice'}]}}

        assert areequal(result, expected_err_json)

    def test_empty_gsim(self, areequal, client):
        '''tests a special case whereby a GSIM is empty (this case raised
        before a PR to smtk repository)'''
        inputdic = {"gsim": ["AbrahamsonEtAl2014",
                             "AbrahamsonEtAl2014NSHMPLower",
                             "AbrahamsonEtAl2014NSHMPMean",
                             "AbrahamsonEtAl2014NSHMPUpper",
                             "AbrahamsonEtAl2014RegCHN",
                             "AbrahamsonEtAl2014RegJPN",
                             "AbrahamsonEtAl2014RegTWN",
                             "AkkarBommer2010SWISS01",
                             "AkkarBommer2010SWISS04",
                             "AkkarBommer2010SWISS08",
                             "AkkarEtAlRepi2014"],
                    "imt": ["PGA", "PGV"], "magnitude": "3:4",
                    "distance": "10:12", "dip": "60",
                    "aspect": "1.5", "rake": "0.0", "ztor": "0.0",
                    "strike": "0.0", "msr": "WC1994",
                    "initial_point": "0 0", "hypocentre_location": "0.5 0.5",
                    "vs30": "760.0", "vs30_measured": True,
                    "line_azimuth": "0.0", "plot_type": "ds"}
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
