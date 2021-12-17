"""Module with the views for the web API (no GUI)"""
import os
from io import StringIO, BytesIO
from typing import Union, Type

import yaml
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from django.forms import Form

from django.http import JsonResponse, HttpRequest
from django.http.multipartparser import MultiPartParser
from django.http.response import HttpResponse
from django.utils.datastructures import MultiValueDict
from django.views.generic.base import View
from django.forms.fields import MultipleChoiceField

from .forms.model_to_data import FlatfileForm
from .forms.model_to_model.trellis import TrellisForm
from .forms.model_to_data.residuals import ResidualsForm
from .forms.model_to_data.testing import TestingForm
from .forms import APIForm


# Set the non-encoded characters. Sources:
# https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/encodeURIComponent#Description
# NOTE THAT THE LAST 5 CHARACTERS ARE NOT SAFE
# ACCORDING TO RFC 3986 EVEN THOUGH THESE CHARACTERS HAVE NOT FORMALIZED
# URI DELIMITING USE. WE MIGHT APPEND [:-5] to QUERY_PARAMS_SAFE_CHARS BUT
# WE SHOULD CHANGE THEN ALSO encodeURIComponent in the javascript files, to
# make it consistent
QUERY_PARAMS_SAFE_CHARS = "-_.~!*'()"


class RESTAPIView(View):
    """Base view for every eGSIM REST API endpoint"""
    # The form class:
    formclass: Type[APIForm] = None
    # the URL(s) endpoints of the API (no paths, no slashes, just the name)
    urls: list[str] = []
    # error codes for general client and server errors:
    CLIENT_ERR_CODE, SERVER_ERR_CODE= 400, 500

    def get(self, request: HttpRequest):
        """processes a get request"""

        form_cls = self.formclass
        # get param names with multiple choices  allowed. For these parameters
        # we'll treat commas as element separators (see below):
        mval_params = set(f for f in form_cls.public_field_names.values()
                          if isinstance(form_cls.declared_fields[f],
                                        (MultipleChoiceField,)))

        ret = {}
        # request.GET is a QueryDict object (see Django doc for details)
        # with percent-encoded characters already decoded
        for param_name, values in request.GET.lists():
            if param_name in mval_params:  # treat commas as element separators:
                newvalues = []
                for val in values:
                    newvalues.extend(val.split(','))
                ret[param_name] = newvalues
            else:
                ret[param_name] = values[0] if len(values) == 1 else values
        return self.response(data=ret)

    def post(self, request: HttpRequest):
        """processes a post request"""
        if request.FILES:
            if not issubclass(self.formclass, FlatfileForm):
                return error_response("The given URL does not support "
                                      "uploaded files", self.CLIENT_ERR_CODE)
            # the parameter is exposed to the user as "flatfile", but
            # internally we use "uploaded_flatfile". Create a new object
            # the same type of request.FILES with key renamed:
            # files = MultiValueDict([('uploaded_flatfile',
            #                          request.FILES.getlist('flatfile'))])
            return self.response(data=request.POST, files=request.FILES)
        else:
            stream = StringIO(request.body.decode('utf-8'))
            inputdict = yaml.safe_load(stream)
            return self.response(data=inputdict)

    @classmethod
    def response(cls, **form_kwargs):
        """process an input Response by calling `self.process` if the input is
        valid according to this class Form (`cls.formclass`). On error, return
        an appropriate JSON response

        :param form_kwargs: keyword arguments to be passed to this class Form
        """
        try:
            form = cls.formclass(**form_kwargs)
            if not form.is_valid():
                err = form.validation_errors()
                return error_response(err['message'], cls.CLIENT_ERR_CODE,
                                      errors=err['errors'])

            response_data = form.response_data
            if form.data_format == form.DATA_FORMAT_CSV:
                return cls.response_text(response_data)
            else:
                return cls.response_json(response_data)
        except ValidationError as cerr:
            return error_response(cerr, cls.CLIENT_ERR_CODE)
        except Exception as err:
            msg = f'Server error ({err.__class__.__name__}): {str(err)}'
            return error_response(msg, cls.SERVER_ERR_CODE)

    @classmethod
    def response_json(cls, response_data: dict):
        """Return a JSON response

        :param response_data: dict representing the form processed data
        """
        return JsonResponse(response_data, safe=False)

    @classmethod
    def response_text(cls, response_data: StringIO):
        """Return a text/csv response

        :param response_data: dict representing the form processed data
        """
        # calculate the content length. FIXME: DO WE NEEED THIS? WHY?
        response_data.seek(0, os.SEEK_END)
        contentlength = response_data.tell()
        response_data.seek(0)
        response = HttpResponse(response_data, content_type='text/csv')
        response['Content-Length'] = str(contentlength)
        return response


# we need to provide the full URL of the views here, because the frontend need
# to inject those URLs (to call them when pressing OK buttons). So prefixes must
# be written here and not in `urls.py`:
API_PATH = 'query'


class TrellisView(RESTAPIView):
    """EgsimQueryView subclass for generating Trellis plots responses"""

    formclass = TrellisForm
    urls = (f'{API_PATH}/trellis', f'{API_PATH}/model-model-comp')


class ResidualsView(RESTAPIView):
    """EgsimQueryView subclass for generating Residuals plot responses"""

    formclass = ResidualsForm
    urls = (f'{API_PATH}/residuals', f'{API_PATH}/model-data-comp')


class TestingView(RESTAPIView):
    """EgsimQueryView subclass for generating Testing responses"""

    formclass = TestingForm
    urls = (f'{API_PATH}/testing', f'{API_PATH}/model-data-test')


def error_response(exception: Union[str, Exception], code=500, **kwargs) -> JsonResponse:
    """Convert the given exception or string message `exception` into a json
    response. the response data will be the dict:
    ```
    {
    "error": {
            "message": exception,
            "code": code,
            **kwargs
        }
    }
    ```
    (see https://google.github.io/styleguide/jsoncstyleguide.xml)

    :param exception: Exception or string. If string, it's the exception
        message. Otherwise, the exception message will be built as str(exception)
    :param code: the response HTTP status code (int, default: 400)
    :param kwargs: other optional arguments which will be inserted in the
        response data dict
    """
    err_body = {**kwargs, 'message': str(exception), 'code': code}
    return JsonResponse({'error': err_body}, safe=False, status=code)
