'''
Tests the client for the trellis service API

Created on 2 Jun 2018

@author: riccardo
'''
import re
import pytest
from mock import patch

from egsim.core.utils import querystring
from egsim.forms.forms import TrellisForm
from egsim.core.smtk import _default_periods_for_spectra
from egsim.forms.fields import TextSepField
from egsim.views import URLS


@pytest.mark.django_db
class Test:
    '''tests the gsim service'''

    url = "/" + URLS.TRELLIS_RESTAPI  # '/query/trellis'
    request_filename = 'request_trellis.yaml'
    csv_expected_text = b'^imt,gsim,magnitude,distance,vs30(,+)\r\n,,,,'
    GSIM, IMT = 'gsim', 'imt'

    def get_figures(self, result):
        '''Returns a list of dicts scanning recursively `result` (the json
        output of a trellis request), where each dict represents
        a trellis plot and has the keys:
        ylabel, yvalues, vs30, magnitude, distance, stdevs
        '''
        ret = []
        for imt_ in result['imts']:
            ret.extend(result[imt_])
        return ret

    @pytest.mark.parametrize('st_dev', [False, True])
    def tst_trellis_dist(self,
                          # pytest fixtures:
                          client, testdata, areequal,
                          # parametrized argument:
                          st_dev):
        '''test trellis distance and distance stdev'''
        inputdic = dict(testdata.readyaml(self.request_filename),
                        plot_type='d', stdev=st_dev)
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        result = resp1.json()
        assert resp1.status_code == 200
        assert areequal(result, resp2.json())
        form = TrellisForm(data=inputdic)
        assert form.is_valid()
        input_ = form.cleaned_data
        assert sorted(result.keys()) == ['PGA', 'PGV', 'SA(0.2)', 'imts',
                                         'xlabel', 'xvalues']
        xvalues = result['xvalues']
        assert len(xvalues) == len(input_['distance']) + 1  # FIXME: should be len(distance)!!!
        figures = self.get_figures(result)
        if st_dev:
            # assert we wrtoe the stdevs:
            assert all(_['stdvalues'] for _ in figures)
            assert all(_['stdlabel'] for _ in figures)
        else:
            # assert we did NOT write stdevs:
            assert not any(_['stdvalues'] for _ in figures)
            assert not any(_['stdlabel'] for _ in figures)
        assert len(figures) == len(input_['magnitude']) * len(input_['imt'])
        for fig in figures:
            yvalues = fig['yvalues']
            assert all(len(yval) == len(xvalues) for yval in yvalues.values())
            assert sorted(yvalues.keys()) == sorted(input_['gsim'])

        # test the text response:
        resp2 = client.post(self.url, data=dict(inputdic, format='text'),
                            content_type='text/csv')
        assert resp2.status_code == 200
        assert re.search(self.csv_expected_text, resp2.content)

    @pytest.mark.parametrize('st_dev', [False, True])
    def tst_trellis_mag(self,
                         # pytest fixtures:
                         client, testdata, areequal,
                         # parametrized argument:
                         st_dev):
        '''test trellis magnitude and magnitude stdev'''
        inputdic = dict(testdata.readyaml(self.request_filename),
                        plot_type='m', stdev=st_dev)
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        result = resp1.json()
        assert resp1.status_code == 200
        assert areequal(result, resp2.json())
        form = TrellisForm(data=inputdic)
        assert form.is_valid()
        input_ = form.cleaned_data
        assert sorted(result.keys()) == ['PGA', 'PGV', 'SA(0.2)', 'imts',
                                         'xlabel', 'xvalues']
        xvalues = result['xvalues']
        assert len(xvalues) == len(input_['magnitude'])
        figures = self.get_figures(result)
        if st_dev:
            # assert we wrtoe the stdevs:
            assert all(_['stdvalues'] for _ in figures)
            assert all(_['stdlabel'] for _ in figures)
        else:
            # assert we did NOT write stdevs:
            assert not any(_['stdvalues'] for _ in figures)
            assert not any(_['stdlabel'] for _ in figures)
        assert len(figures) == len(input_['distance']) * len(input_['imt'])
        for fig in figures:
            yvalues = fig['yvalues']
            assert all(len(yval) == len(xvalues) for yval in yvalues.values())
            assert sorted(yvalues.keys()) == sorted(input_['gsim'])

        # test the text response:
        resp2 = client.post(self.url, data=dict(inputdic, format='text'),
                            content_type='text/csv')
        assert resp2.status_code == 200
        assert re.search(self.csv_expected_text, resp2.content)
        ref_resp = resp2.content
        # test different text formats
        for text_sep, symbol in TextSepField._base_choices.items():
            resp3 = client.post(self.url, data=dict(inputdic, format='text',
                                                    text_sep=text_sep),
                                content_type='text/csv')
            assert resp3.status_code == 200
            real_content = sorted(_ for _ in resp3.content.split(b'\r\n'))
            expected_content = \
                sorted(_ for _ in
                       ref_resp.replace(b',',
                                        symbol.encode('utf8')).split(b'\r\n'))
            if text_sep != 'space':
                # FIXME: we do not test the space because quotation marks
                # are involved and thus the text comparison is harder.
                # We should read it with csv...
                assert real_content == expected_content

        resp3 = client.post(self.url, data=dict(inputdic, format='text',
                                                text_sep='semicolon',
                                                text_dec='comma'),
                            content_type='text/csv')
        assert resp3.status_code == 200
        real_content = sorted(_ for _ in resp3.content.split(b'\r\n'))
        expected_content = \
            sorted(_ for _ in
                   ref_resp.replace(b',', b';').replace(b'.', b',').
                   split(b'\r\n'))
        # asserting all rows are equal fails. This might be due to rounding
        # errors, thus assert only first line is equal. Not really sound,
        # but better than nothing
        assert real_content[0] == expected_content[0]

        resp3 = client.post(self.url, data=dict(inputdic, format='text',
                                                text_dec='comma'),
                            content_type='text/csv')
        assert resp3.status_code == 400
        expected_json = {
            'error': {
                'code': 400,
                'message': 'Invalid input in text_sep, text_dec',
                'errors': [
                    {
                        'domain': 'text_sep',
                        'message': ("'text_sep' must differ from"
                                    " 'text_dec' in 'text' format"),
                        'reason': 'conflicting values'
                    },
                    {
                        'domain': 'text_dec',
                        'message': ("'text_sep' must differ from"
                                    " 'text_dec' in 'text' format"),
                        'reason': 'conflicting values'
                    }
                ]
            }
        }
        assert areequal(resp3.json(), expected_json)

    @pytest.mark.parametrize('st_dev', [False, True])
    def test_trellis_spectra(self,
                             # pytest fixtures:
                             client, testdata, areequal,
                             # parametrized argument:
                             st_dev):
        '''test trellis magnitude-distance spectra and magnitude-distance
        stdev'''
        inputdic = dict(testdata.readyaml(self.request_filename),
                        plot_type='s', stdev=st_dev)
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        result = resp1.json()
        assert resp1.status_code == 200
        assert areequal(result, resp2.json())
        form = TrellisForm(data=inputdic)
        assert form.is_valid()
        input_ = form.cleaned_data
        assert sorted(result.keys()) == ['SA', 'imts', 'xlabel', 'xvalues']
        xvalues = result['xvalues']
        assert len(xvalues) == len(_default_periods_for_spectra())
        figures = self.get_figures(result)
        if st_dev:
            # assert we wrtoe the stdevs:
            assert all(_['stdvalues'] for _ in figures)
            assert all(_['stdlabel'] for _ in figures)
        else:
            # assert we did NOT write stdevs:
            assert not any(_['stdvalues'] for _ in figures)
            assert not any(_['stdlabel'] for _ in figures)
        assert len(figures) == \
            len(input_['distance']) * len(input_['magnitude'])
        for fig in figures:
            yvalues = fig['yvalues']
            assert all(len(yval) == len(xvalues) for yval in yvalues.values())
            assert sorted(yvalues.keys()) == sorted(input_['gsim'])

        # test the text response:
        resp2 = client.post(self.url, data=dict(inputdic, format='text'),
                            content_type='text/csv')
        assert resp2.status_code == 200
        assert re.search(self.csv_expected_text, resp2.content)

        # test for the frontend: supply SA incorrectly but check that it's
        # ignored
        resp1 = client.post(self.url, data=dict(inputdic, imt='SA',
                                                sa_period='(set'),
                            content_type='application/json')
        result = resp1.json()
        assert resp1.status_code == 200
        # supply also wrong imt (ignored, SA is used):
        resp1 = client.post(self.url, data=dict(inputdic, imt='PGV',
                                                sa_period='(set'),
                            content_type='application/json')
        result = resp1.json()
        assert resp1.status_code == 200

    def test_error(self,
                   # pytest fixtures:
                   client, areequal):
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
            "stdev": True,
            "plot_type": "d"
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

    def test_empty_gsim(self,
                        # pytest fixtures:
                        areequal, client):
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
            "stdev": True,
            "plot_type": "d"
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
        figures = self.get_figures(result)
        assert any(_['yvalues']['AkkarBommer2010SWISS01'] == []
                   for _ in figures)

    @pytest.mark.parametrize('vs30, z1pt0, z2pt5',
                             [(120, [1, 2.56], [3, 4]),
                              ([1.4, 2, 3], [1, 2], [3.0, 4]),
                              ([1, 20], 1, 3.0)])
    def test_mismatch_z1pt0_z2pt5(self,
                                  # pytest fixtures:
                                  areequal, client,
                                  # parametrized arguments:
                                  vs30, z1pt0, z2pt5):
        '''tests mismatches between vs30 and related parameters'''
        inputdic = {
            "gsim": [
                "AbrahamsonEtAl2014",
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
            "vs30": vs30,
            "vs30_measured": True,
            "line_azimuth": "0.0",
            "stdev": True,
            "plot_type": "d",
            "z1pt0": z1pt0,
            'z2pt5': z2pt5
        }
        resp1 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        result = resp1.json()
        expected_str = "%d-elements vector" % len(vs30) \
            if hasattr(vs30, '__len__') else 'scalar'
        expected_json = {
            'error': {
                'code': 400,
                'message': 'Invalid input in z1pt0, z2pt5',
                'errors': [
                    {
                        'domain': 'z1pt0',
                        'message': ('value must be consistent with '
                                    'vs30 (%s)' % expected_str),
                        'reason': 'invalid'
                    },
                    {
                        'domain': 'z2pt5',
                        'message': ('value must be consistent with '
                                    'vs30 (%s)' % expected_str),
                        'reason': 'invalid'
                    }
                ]
            }
        }
        assert areequal(result, expected_json)
        assert resp1.status_code == 400

        # now test all vectors of same length:
        inputdic['vs30'] = inputdic['z1pt0'] = inputdic['z2pt5'] = [760, 800]
        resp1 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        assert resp1.status_code == 200

    def test_mismatching_imt_gsim(self,
                                  # pytest fixtures:
                                  areequal, client):
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
            "stdev": True,
            "plot_type": "d"
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
