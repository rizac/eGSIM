"""
Tests the client for the residuals service API

Created on 22 Oct 2018

@author: riccardo
"""
import re
import json
import pytest

from unittest.mock import patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.datastructures import MultiValueDict

from egsim.api.forms.flatfile.residuals import ResidualsForm
from egsim.api.views import ResidualsView, RESTAPIView
from egsim.app.templates.egsim import URLS


@pytest.mark.django_db
class Test:
    """tests the residuals service"""

    def test_download_cfg(self,
                          # pytest fixtures:
                          testdata, areequal, client):
        url = f'{URLS.DOWNLOAD_REQUEST}/residuals/filename.yaml'
        request_filename = 'request_residuals.yaml'
        inputdic = testdata.readyaml(request_filename)
        # no flatfile, uploaded flatfile:
        inputdic['plot_type'] = 'res'
        inputdic2 = dict(inputdic)
        # inputdic2.pop('flatfile')
        resp2 = client.post(url, data=json.dumps(inputdic2),
                            content_type='application/json')
        asd = 9
