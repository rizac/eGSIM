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
    dict_keys = {
        'defined_for', 'description', 'hazard_source_models',
        'requires', 'sa_period_limits'
    }
    data = {'name': ['CauzziEtAl2014']}  # "name" or "model" are equivalent param names
    response = client.post(f"/{MODEL_INFO}",
                           json.dumps(data),
                           content_type="application/json")
    assert response.status_code == 200
    resp_json = response.json()
    assert sorted(resp_json.keys()) == ['CauzziEtAl2014']
    assert all(
        isinstance(v, dict) and set(v.keys()) == dict_keys for v in resp_json.values()
    )
    assert all(v['hazard_source_models'] is None for v in resp_json.values())

    data = {'model': ['BindiEtAl2014Rjb', 'CauzziEtAl2014']}
    response = client.post(f"/{MODEL_INFO}",
                           json.dumps(data),
                           content_type="application/json")
    assert response.status_code == 200
    resp_json = response.json()
    assert sorted(resp_json.keys()) == ['BindiEtAl2014Rjb', 'CauzziEtAl2014']
    assert all(
        isinstance(v, dict) and set(v.keys()) == dict_keys for v in resp_json.values()
    )
    assert all(v['hazard_source_models'] is None for v in resp_json.values())

    data = {'model': ['zww', 'CauzziEtAl2014']}
    response = client.post(f"/{MODEL_INFO}",
                           json.dumps(data),
                           content_type="application/json")
    assert response.status_code == 400
    assert error_message(response) == 'model: invalid model(s) zww'

    # partial names: raises (NOTE: we can also supply "name" instead pf "model"):
    data = {'name': 'cauzzi'}
    response = client.post(f"/{MODEL_INFO}",
                           json.dumps(data),
                           content_type="application/json")
    assert response.status_code == 200

    # partial names: raises (NOTE: we can also supply "name" instead pf "model"):
    data = {'lat': 45, 'lon': 47}
    response = client.post(f"/{MODEL_INFO}",
                           json.dumps(data),
                           content_type="application/json")
    resp_json = response.json()
    assert list(resp_json) == ['ESHM20Craton']
    assert all(len(v['hazard_source_models']) > 0 for v in resp_json.values())
    assert response.status_code == 200

    # germany:
    data = {'lat': 50, 'lon': 10}
    response = client.post(f"/{MODEL_INFO}",
                           json.dumps(data),
                           content_type="application/json")
    resp_json = response.json()
    assert list(resp_json) == ['AkkarBommer2010', 'AkkarEtAlRhyp2014',
                               'BindiEtAl2014Rhyp', 'BindiEtAl2017Rhypo',
                               'Campbell2003SHARE', 'CauzziEtAl2014RhypoGermany',
                               'CauzziFaccioli2008', 'ChiouYoungs2008',
                               'DerrasEtAl2014RhypoGermany', 'ESHM20Craton',
                               'KothaEtAl2020ESHM20', 'ToroEtAl2002SHARE']
    assert all(len(v['hazard_source_models']) > 0 for v in resp_json.values())
    assert response.status_code == 200


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
