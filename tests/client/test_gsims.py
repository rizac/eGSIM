'''
Tests the client for the gsims service

Created on 22 Oct 2018

@author: riccardo
'''
import pytest

from egsim.core.utils import querystring, EGSIM
from egsim.models import aval_gsims


@pytest.mark.django_db
class Test:
    '''tests the gsim service'''

    url = '/query/gsims'
    request_filename = 'request_gsims.yaml'

    def test_gsims_service(self, testdata, areequal,  # django_db_setup,
                           client):
        '''tests the gsims API service.
        :param requesthandler: pytest fixture which handles the read from the yaml file
            request.yaml which MUST  BE INSIDE this module's directory
        :param areequal: pytest fixture qith a method `equal` that tests for object equality
            with optional error tolerances for numeric arrays and other utilities (e.g. lists
            with same elements in different orders are equal)
        :param client: a Django test.Client object automatically created in conftest. This
            function is iteratively called with a list of different Clients created in conftest.py
        '''
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

    def test_gsims_service_no_result_wrong_trt(self, testdata, areequal,
                                               # django_db_setup,
                                               client):
        '''tests the gsims API service.
        :param requesthandler: pytest fixture which handles the read from the yaml file
            request.yaml which MUST  BE INSIDE this module's directory
        :param areequal: pytest fixture qith a method `equal` that tests for object equality
            with optional error tolerances for numeric arrays and other utilities (e.g. lists
            with same elements in different orders are equal)
        :param client: a Django test.Client object automatically created in conftest. This
            function is iteratively called with a list of different Clients created in conftest.py
        '''
        inputdic = testdata.readyaml(self.request_filename)
        inputdic.update(trt='stable_continental_region')
        # use a key which is not in the defined sets of OpenQuake's TRTs:
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        resp2 = client.post(self.url, data=inputdic,
                            content_type='application/json')
        assert resp1.status_code == resp2.status_code == 400
        assert areequal(resp1.json(), resp2.json())
        assert isinstance(resp1.json(), dict) and resp1.json()['error']['code'] == 400

    def test_gsims_service_imt_no_match(self, testdata, areequal,
                                        # django_db_setup,
                                        client):
        '''tests the gsims API service.
        :param requesthandler: pytest fixture which handles the read from the yaml file
            request.yaml which MUST  BE INSIDE this module's directory
        :param areequal: pytest fixture qith a method `equal` that tests for object equality
            with optional error tolerances for numeric arrays and other utilities (e.g. lists
            with same elements in different orders are equal)
        :param client: a Django test.Client object automatically created in conftest. This
            function is iteratively called with a list of different Clients created in conftest.py
        '''
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
