"""
Tests for app requests and functions
"""
from urllib.error import URLError

import json
import pytest
import urllib.request

from django.http import HttpResponse

from egsim.api.urls import MODEL_INFO

from django.test.client import Client

GSIM, IMT = 'gsim', 'imt'

tests_are_not_online = False
try:
    with urllib.request.urlopen('https://egsim.gfz-potsdam.de/') as response:
        pass  # response.read(1)
except URLError as exc:
    tests_are_not_online = True


def error_message(response: HttpResponse):
    return response.content.decode(response.charset)


@pytest.mark.django_db
def test_model_info():
    client = Client()
    data = {'model': ['CauzziEtAl2014']}
    response = client.post(f"/{MODEL_INFO}",
                           json.dumps(data),
                           content_type="application/json")
    assert response.status_code == 200
    assert sorted(response.json().keys()) == ['CauzziEtAl2014']
    assert all(isinstance(v, dict) and sorted(v.keys()) == ['doc', 'imts', 'props']
               for v in response.json().values())

    data = {'model': ['BindiEtAl2014Rjb', 'CauzziEtAl2014']}
    response = client.post(f"/{MODEL_INFO}",
                           json.dumps(data),
                           content_type="application/json")
    assert response.status_code == 200
    assert sorted(response.json().keys()) == ['BindiEtAl2014Rjb', 'CauzziEtAl2014']
    assert all(isinstance(v, dict) and sorted(v.keys()) == ['doc', 'imts', 'props']
               for v in response.json().values())

    data = {'model': ['x', 'CauzziEtAl2014']}
    response = client.post(f"/{MODEL_INFO}",
                           json.dumps(data),
                           content_type="application/json")
    assert response.status_code == 400
    assert error_message(response) == 'model: invalid model(s) x'


def test_not_found(client):
    response = client.post(f"/absgdhfgrorvjlkfn elfnbvenbv",
                           json.dumps({}),
                           content_type="application/json")
    assert response.status_code == 404


def test_testresponse_url(client):
    for x in [200, 302, 404, 502]:
        response = client.post(f"/test_response/{x}",
                               json.dumps({}),
                               content_type="application/json")
        assert response.status_code == x
