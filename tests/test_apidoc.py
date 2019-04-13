'''
Tests the eGSIM Django commands

Created on 6 Apr 2019

@author: riccardo
'''
import os
import pytest

from mock import patch


@pytest.mark.django_db
def test_apidoc(client):
    '''Test gmdb_esm command (and consequently, also gmbd command)'''
    result = client.get('/service/apidoc')
    assert result.status_code == 200
    # stupid assert (better than nothing for the moment):
    assert b"[eGSIM domain URL]/query" in result.content
