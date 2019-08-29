'''
Tests the eGSIM Django http responses (HTTP pags)

Created on 6 Apr 2019

@author: riccardo
'''
import pytest


@pytest.mark.django_db
class Test:

    def test_apidoc(self,
                    # pytest fixtures:
                    testdata, client):  # pylint: disable=unused-argument
        '''Test apidoc page generation'''
        result = client.get('/pages/apidoc')
        assert result.status_code == 200
        # check we do not have django undefined variables:
        # (we set somewhere in the code to display when a template
        # variable is not found. and Django prints <VARNAME> NOT FOUND
        # in case. Thus:
        assert b" NOT FOUND" not in result.content
        assert b"UNKNOWN_TYPE" not in result.content

    def test_main(self,
                  # pytest fixtures:
                  testdata, client):
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

    def test_home(self,
                  # pytest fixtures:
                  testdata, client):
        '''Test home page generation'''
        result = client.get('/pages/home')
        assert result.status_code == 200
