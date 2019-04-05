'''
Tests the client for the gsims service

Created on 22 Oct 2018

@author: riccardo
'''
from egsim.core.utils import querystring, EGSIM


class Test:

    url = '/query/gsims'
    request_filename = 'request_gsims.yaml'

    def test_gsims_service(self, testdata, areequal, client):
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
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        resp2 = client.get(self.url, data=inputdic)

        assert resp1.status_code == resp2.status_code == 200
        assert areequal(resp1.json(), resp2.json())

        expected_gsims = [k for k, v in EGSIM.aval_gsims.items() if v.trt == inputdic['trt']]
        assert sorted(resp1.json()) == sorted(expected_gsims)

    def test_gsims_service_no_result_wrong_trt(self, testdata, areequal, client):
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
        resp2 = client.get(self.url, data=inputdic)

        assert resp1.status_code == resp2.status_code == 400

        assert areequal(resp1.json(), resp2.json())
        assert isinstance(resp1.json(), dict) and resp1.json()['error']['code'] == 400

    def test_gsims_service_imt_no_match(self, testdata, areequal, client):
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
        expected_gsims = [k for k, v in EGSIM.aval_gsims.items() if v.trt == inputdic['trt']]
        # use a key which is not in the defined sets of OpenQuake's TRTs.
        inputdic.update(imt='*KW?,[]')
        resp1 = client.get(querystring(inputdic, baseurl=self.url))
        # use another key which is not in the defined sets of OpenQuake's TRTs:
        inputdic.update(imt='KW?')
        resp2 = client.get(querystring(inputdic, baseurl=self.url))
    
        assert areequal(resp1.json(), resp2.json())
        # no gsim found:
        assert resp1.status_code == resp2.status_code == 200
        # no gsim found:
        assert resp1.json() == resp2.json() == []
