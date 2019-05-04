'''
Tests the eGSIM Django http responses (HTTP pags)

Created on 6 Apr 2019

@author: riccardo
'''
import os
import pytest

from mock import patch


@pytest.mark.django_db
def test_apidoc(client):
    '''Test apidoc page generation'''
    result = client.get('/pages/apidoc')
    assert result.status_code == 200
    # stupid assert (better than nothing for the moment):
    assert b"[eGSIM domain URL]/query" in result.content
    # check we do not have django undefined variables:
    assert b" NOT FOUND" not in result.content


@pytest.mark.django_db
def test_main(client):
    '''Test main page generation'''
    result = client.get('/')
    assert result.status_code == 302
    # stupid assert (better than nothing for the moment):
    assert result.content == b''

    # now follow redirect:
    result = client.get('/', follow=True)
    assert result.status_code == 200
    # stupid assert (better than nothing for the moment):
    assert b'<title>eGSIM</title>' in result.content


@pytest.mark.django_db
def test_home(client):
    '''Test home page generation'''
    result = client.get('/pages/home')
    assert result.status_code == 200
