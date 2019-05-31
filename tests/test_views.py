'''
Tests the "remaining" views (excluding those used for the REST API and those
used to display static HTML pages)

Created on 6 Apr 2019

@author: riccardo
'''
import os
import pytest
from mock import patch

from egsim.views import URLS


@pytest.mark.django_db
class Test:

    @pytest.mark.parametrize('filename', ['filename.json', 'filename.yaml'])
    def test_downloadrequest(self, filename,
                             # pytest fixtures:
                             testdata, client):
        '''Test the view for downloading a request in json or yaml format'''
        if os.path.splitext(filename) == '.json':
            ctype = 'application/json' 
        else:
            ctype = 'application/x-yaml'
        url = URLS.TRELLIS_DOWNLOAD_REQ
        inputdic = testdata.readyaml('request_trellis.yaml')
        result = client.post("/" + url + "/" + filename, data=inputdic,
                             content_type=ctype)
        assert result.status_code == 200
        assert result._headers['content-disposition'][1].endswith(filename)
        # FIXME: better assertion checks?

    def test_downloadresponse_astext(self,
                                     # pytest fixtures:
                                     testdata, client):
        '''Test the view for downloading data as text/csv from the broswer'''
        inputdic = testdata.readyaml('request_trellis.yaml')
        result = client.post("/" + URLS.TRELLIS_RESTAPI, data=inputdic,
                             content_type='application/json')
        outdict = result.json()
        for url in [URLS.TRELLIS_DOWNLOAD_ASTEXT,
                    URLS.TRELLIS_DOWNLOAD_ASTEXT_EU]:
            inputdic = testdata.readyaml('request_trellis.yaml')
            filename = 'prova.csv'
            result = client.post("/" + url + "/" + filename, data=outdict,
                                 content_type="text/csv")
            assert result.status_code == 200
            # stupid assert (better than nothing for the moment):
            assert result.content
            assert result._headers['content-disposition'][1].endswith(filename)
        # FIXME: better assertion checks?

    def test_get_tr(self,
                    # pytest fixtures:
                    client):
        '''Test the view returning all the tectonic regionalisation models'''
        result = client.get('/' + URLS.GSIMS_TR,
                            content_type='application/json')
        assert result.status_code == 200
