"""Module with the views for the web API (no GUI)"""
import os
from io import StringIO
from typing import Union

import yaml

from django.http import JsonResponse
from django.http.response import HttpResponse
from django.views.generic.base import View
from django.forms.fields import MultipleChoiceField

# from egsim.core.responseerrors import (exc2json, invalidform2json,
#                                        requestexc2json)
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


class RESTAPIView(View):  #, metaclass=EgsimQueryViewMeta):
    """Base view for every eGSIM REST API endpoint"""
    # The form class:
    formclass: APIForm = None
    # the URL(s) endpoints of the API (no paths, no slashes, just the name)
    urls: list[str] = []

    def get(self, request):
        """processes a get request"""
        try:
            # get param names with multiple choices allowed, which might be
            # typed with commas and thus splitted:
            mval_params = set(n for n, f in self.formclass.declared_fields.items()
                              if isinstance(f, (MultipleChoiceField,)))
            #  get to dict:
            #  Note that percent-encoded characters are decoded automatically
            ret = {}
            # https://docs.djangoproject.com/en/2.2/ref/request-response/#django.http.QueryDict.lists
            for param_name, values in request.GET.lists():
                if param_name in mval_params:
                    newvalues = []
                    for val in values:
                        newvalues.extend(val.split(','))
                    ret[param_name] = newvalues
                else:
                    ret[param_name] = values[0] if len(values) == 1 else values
            return self.response(ret)

        except Exception as err:
            msg = f'Error in GET request (f{str(err) or err.__class__.__name__})'
            return error_response(msg, 500)

    def post(self, request):
        """processes a post request"""
        try:
            stream = StringIO(request.body.decode('utf-8'))
            return self.response(yaml.safe_load(stream))
        except Exception as err:
            msg = f'Error in POST request (f{str(err) or err.__class__.__name__})'
            return error_response(msg, 500)

    @classmethod
    def response(cls, inputdict):
        """process an input dict `inputdict`, returning a response object.
        Calls `self.process` if the input is valid according to
        `cls.formclass`. On error, returns an appropriate json response
        (see `module`:core.responseerrors)
        """
        form = cls.formclass(data=inputdict)  # noqa
        if not form.is_valid():
            verr = form.validation_errors()
            return error_response(verr['message'], verr['code'],
                                  errors=verr['errors'])

        response_data = form.response_data()
        if form.get_data_format == form.DATA_FORMAT_TEXT:
            return cls.response_text(response_data)
        elif form.get_data_format == form.DATA_FORMAT_JSON:
            return cls.response_json(response_data)
        else:
            return error_response('data format "%s" not implemented' %
                                  form.get_data_format)

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


# class GmdbPlotView(RESTAPIView):
#     """EgsimQueryView subclass for generating Gmdb's
#        magnitude vs distance plots responses"""
#
#     formclass = GmdbPlotForm


def error_response(exception: Union[str, Exception], code=400, **kwargs) -> JsonResponse:
    """Convert the given exception or string message `exception` into a json
    response. the response data will be the dict:
    ```
    {
     'error':{
              'message': exception,
              'code': code,
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

# FIXME REMOVE
# class EgsimQueryViewMeta(type):
#     """metaclass for EgsimChoiceField subclasses. Populates the class attribute
#     `multichoice_params` with fields which accept array-like values
#     """
#     def __init__(cls, name, bases, nmspc):
#         super(EgsimQueryViewMeta, cls).__init__(name, bases, nmspc)
#         formclass = cls.formclass  # noqa
#         cls.multichoice_params = set()
#         fields = {} if formclass is None else formclass.declared_fields
#         for name, field in fields.items():
#             if isinstance(field, (MultipleChoiceField,)):
#                 cls.multichoice_params.add(name)
#
