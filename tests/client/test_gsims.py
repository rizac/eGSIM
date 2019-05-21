'''
Tests the client for the gsims service API

Created on 22 Oct 2018

@author: riccardo
'''
import pytest

from egsim.core.utils import querystring
from egsim.models import aval_gsims


@pytest.mark.django_db
class Test:
    '''tests the gsim service'''

    url = '/query/gsims'
    request_filename = 'request_gsims.yaml'

    def test_gsims_service(self,
                           # pytest fixtures:
                           testdata, areequal, client):
        '''tests the gsims API service'''
        inputdic = testdata.readyaml(self.request_filename)
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        assert resp1.status_code == resp2.status_code == 200
        assert areequal(resp1.json(), resp2.json())

        expected_gsims = [k[0] for k in aval_gsims(asjsonlist=True)
                          if k[2] == inputdic['trt']]
        assert sorted(resp1.json()) == sorted(expected_gsims)

        # now try to supply two filters on gsim:
        expected_gsims = [_ for _ in expected_gsims if _[0] in ('A',)]
        inputdic['gsim'] = expected_gsims
        resp1 = client.get(self.url, data=inputdic)
        inputdic['gsim'] = 'A*'
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        assert resp1.status_code == resp2.status_code == 200
        assert areequal(resp1.json(), resp2.json())
        assert sorted(resp1.json()) == sorted(resp1.json()) == \
            sorted(expected_gsims)

        # test text format:
        resp2 = client.post(self.url, data=dict(inputdic, format='text'),
                            content_type='text/csv')
        assert resp2.status_code == 200
        assert areequal(resp1.json(), [_.decode('utf8')
                                       for _ in resp2.content.split()])

    def test_gsims_service_no_result_wrong_trt(self,
                                               # pytest fixtures:
                                               testdata, areequal, client):
        '''tests the gsims API service with a wrong tectonic region type'''
        inputdic = testdata.readyaml(self.request_filename)
        inputdic.update(trt='stable_continental_region')
        # use a key which is not in the defined sets of OpenQuake's TRTs:
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        assert resp1.status_code == resp2.status_code == 400
        assert areequal(resp1.json(), resp2.json())
        assert isinstance(resp1.json(), dict) and \
            resp1.json()['error']['code'] == 400

    def test_gsims_service_imt_no_match(self,
                                        # pytest fixtures:
                                        testdata, areequal, client):
        '''tests the gsims API service with no match for imt provided with
        wildcards'''
        inputdic = testdata.readyaml(self.request_filename)
        # use a key which is not in the defined sets of OpenQuake's IMTs.
        inputdic.update(imt='*KW?,[]')
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        # use another key which is not in the defined sets of OpenQuake's IMTs:
        inputdic.update(imt='KW?')
        resp2 = client.get(querystring(inputdic, baseurl=self.url))

        assert areequal(resp1.json(), resp2.json())
        # no gsim found:
        assert resp1.status_code == resp2.status_code == 200
        # no gsim found:
        assert resp1.json() == resp2.json() == []
