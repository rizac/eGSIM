'''
Tests the "remaining" views (excluding those used for the REST API and those
used to display static HTML pages)

Created on 6 Apr 2019

@author: riccardo
'''
import os
import json
import pytest
from mock import patch

from egsim.views import URLS, KEY


@pytest.mark.django_db
class Test:

    @pytest.mark.parametrize('filename', ['filename.json', 'filename.yaml'])
    def test_downloadrequest(self, filename,
                             # pytest fixtures:
                             testdata, client):
        '''Test the view for downloading a request in json or yaml format'''
        # testing for 'testing' and 'residuals' has the typical problem of
        # mocking the gmdb, which is a big overhead: let's test for trellis
        # only:
        if os.path.splitext(filename)[1] == '.json':
            ctype = 'text/javascript'
        else:
            ctype = 'application/x-yaml'
        url = "/%s/%s" % (URLS.DOWNLOAD_CFG, KEY.TRELLIS)
        inputdic = testdata.readyaml('request_trellis.yaml')
        result = client.post(url + "/" + filename, data=inputdic,
                             content_type=ctype)
        assert result.status_code == 200
        assert result._headers['content-disposition'][1].endswith(filename)
        assert ctype == result._headers['content-type'][1]
        # FIXME: better assertion checks?

    @pytest.mark.parametrize('base_url', [URLS.DOWNLOAD_ASTEXT,
                                          URLS.DOWNLOAD_ASTEXT_EU])
    def test_downloadresponse_astext(self, base_url,
                                     # pytest fixtures:
                                     testdata, client):
        '''Test the view for downloading data as text/csv from the broswer'''
        # testing for 'testing' and 'residuals' has the typical problem of
        # mocking the gmdb, which is a big overhead: let's test for trellis
        # only:
        inputdic = testdata.readyaml('request_trellis.yaml')
        result = client.post("/" + URLS.TRELLIS_RESTAPI, data=inputdic,
                             content_type='application/json')
        outdict = result.json()
        filename = 'prova.csv'
        url = "/%s/%s/%s" % (base_url, KEY.TRELLIS, filename)
        inputdic = testdata.readyaml('request_trellis.yaml')
        result = client.post(url, data=outdict,
                             content_type="text/csv")
        assert result.status_code == 200
        # stupid assert (better than nothing for the moment):
        assert result.content
        assert result._headers['content-disposition'][1].endswith(filename)
        assert "text/csv" == result._headers['content-type'][1]
        # FIXME: better assertion checks?

    def test_get_tr(self,
                    # pytest fixtures:
                    client):
        '''Test the view returning all the tectonic regionalisation models'''
        result = client.get('/' + URLS.GSIMS_TR,
                            content_type='application/json')
        assert result.status_code == 200

    @pytest.mark.parametrize('fileprefix, urlkey',
                             [('trellis', KEY.TRELLIS),
                              ('residuals', KEY.RESIDUALS)])
    def test_downloadimage(self, fileprefix, urlkey,
                           # pytest fixtures:
                           testdata, client):
        root = testdata.path('plotly')
        jsonfiles = [_ for _ in os.listdir(root) if _.startswith(fileprefix)]
        # sort file by size (see next comment)
        jsonfiles.sort(key=lambda _: os.path.getsize(os.path.join(root, _)))
        for i, jsonf in enumerate(jsonfiles):
            formats = ['png', 'pdf']
            # try eps and svg only for first file (otherwise tests are too
            # long). We use the smallest file for that (the first) to speed up
            # even more
            if i == 0:
                formats += ['eps', 'svg']
            with open(os.path.join(root, jsonf), encoding='utf-8') as fp:
                jsondata = json.load(fp)
            url = "%s/%s" % (URLS.DOWNLOAD_ASIMG, urlkey)
            expected_filename = fileprefix

            jsondata['width'] = 900
            jsondata['height'] = 650

            for format in formats:
                result = client.post("/%s.%s" % (url, format),
                                     data=json.dumps(jsondata),
                                     content_type='application/json')
                assert result.status_code == 200
                # stupid assert (better than nothing for the moment):
                assert result.content
                expected_content_type = format
                if format == 'eps':
                    expected_content_type = 'postscript'
                assert expected_content_type in \
                    result._headers['content-type'][1]
                assert result._headers['content-disposition'][1].\
                    endswith("%s.%s" % (expected_filename, format))
                assert int(result._headers['content-length'][1]) > 0
