'''
Tests the client for the gsims service

Created on 22 Oct 2018

@author: riccardo
'''
from django.test.client import Client
import pytest


def test_gsims_service(requesthandler, comparator, client):
    '''tests the gsims API service.
    :param requesthandler: pytest fixture which handles the read from the yaml file
        request.yaml which MUST  BE INSIDE this module's directory
    :param comparator: pytest fixture qith a method `equal` that tests for object equality
        with optional error tolerances for numeric arrays and other utilities (e.g. lists
        with same elements in different orders are equal)
    :param client: a Django test.Client object automatically created in conftest. This
        function is iteratively called with a list of different Clients created in conftest.py
    '''
    url = '/query/gsims'

    resp1 = client.get(requesthandler.querystr(baseurl=url))
    resp2 = client.get(url, data=requesthandler.dict())

    assert comparator.equal(resp1.json(), resp2.json())
    assert len(resp1.json()) > 0


def test_gsims_service_no_result_wrong_trt(requesthandler, comparator, client):
    '''tests the gsims API service.
    :param requesthandler: pytest fixture which handles the read from the yaml file
        request.yaml which MUST  BE INSIDE this module's directory
    :param comparator: pytest fixture qith a method `equal` that tests for object equality
        with optional error tolerances for numeric arrays and other utilities (e.g. lists
        with same elements in different orders are equal)
    :param client: a Django test.Client object automatically created in conftest. This
        function is iteratively called with a list of different Clients created in conftest.py
    '''
    url = '/query/gsims'

    # use a key which is not in the defined sets of OpenQuake's TRTs:
    resp1 = client.get(requesthandler.querystr(baseurl=url, trt='stable_continental_region'))
    resp2 = client.get(url, data=requesthandler.dict(trt='stable_continental_region'))

    assert comparator.equal(resp1.json(), resp2.json())
    assert isinstance(resp1.json(), dict) and resp1.json()['error']['code'] == 400


def test_gsims_service_no_result_wrong_imt(requesthandler, comparator, client):
    '''tests the gsims API service.
    :param requesthandler: pytest fixture which handles the read from the yaml file
        request.yaml which MUST  BE INSIDE this module's directory
    :param comparator: pytest fixture qith a method `equal` that tests for object equality
        with optional error tolerances for numeric arrays and other utilities (e.g. lists
        with same elements in different orders are equal)
    :param client: a Django test.Client object automatically created in conftest. This
        function is iteratively called with a list of different Clients created in conftest.py
    '''
    url = '/query/gsims'

    # use a key which is not in the defined sets of OpenQuake's TRTs:
    resp1 = client.get(requesthandler.querystr(baseurl=url, imt='*KW?,[]'))
    resp2 = client.get(url, data=requesthandler.dict(imt='KW?'))

    assert comparator.equal(resp1.json(), resp2.json())
    assert len(resp1.json()) == 0

