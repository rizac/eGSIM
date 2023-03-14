"""Module with the views for the web API (no GUI)"""
import os
from io import StringIO
from typing import Union, Type

import yaml
from django.core.exceptions import ValidationError

from django.http import JsonResponse, HttpRequest, QueryDict
from django.http.response import HttpResponse
from django.views.generic.base import View
from django.forms.fields import MultipleChoiceField

from .forms.fields import NArrayField, split_string
from .forms.flatfile import FlatfileForm
from .forms.trellis import TrellisForm
from .forms.flatfile.residuals import ResidualsForm
from .forms.flatfile.testing import TestingForm
from .forms import APIForm


class RESTAPIView(View):
    """Base view for every eGSIM REST API endpoint. Typical usage:

    1. For usage as view in `urls.py`: subclass and provide the relative `formclass`
    2. For usage inside a `views.py` function, to process data with a `APIForm`
       class `form_cls` (note: class not object):
       ```
       def myview(request):
           return RESTAPIView.as_view(formclass=form_cls)(request)
       ```
    """
    # The APIForm of this view, to be set in subclasses:
    formclass: Type[APIForm] = None
    # the URL(s) endpoints of the API (no paths, no slashes, just the name):
    urls: list[str] = []
    # error codes for general client and server errors:
    CLIENT_ERR_CODE, SERVER_ERR_CODE = 400, 500

    def parse_query_dict(self, querydict: QueryDict, nulls=("null",)) \
            -> dict[str, Union[str, list[str]]]:
        """parse the given query dict and returns a Python dict

        :param querydict: a QueryDict resulting from an HttpRequest.POST or
            HttpRequest.GET, with percent-encoded characters already decoded
        :param nulls: tuple/list/set of strings to be converted to None. Defaults
            to ("null", )
        """
        form_cls = self.formclass

        multi_params = set()
        for field_name, field, param_names in form_cls.field_iterator():
            if isinstance(field, (MultipleChoiceField, NArrayField)):
                multi_params.update(param_names)

        ret = {}
        for param_name, values in querydict.lists():
            if param_name in multi_params:
                new_value = []
                for val in values:
                    new_value.extend(split_string(val))
            else:
                new_value = values[0] if len(values) == 1 else values
            if param_name in ret:
                old_value = ret[param_name]
                if not isinstance(old_value, list):
                    old_value = [old_value]
                if isinstance(new_value, list):
                    old_value.extend(None if v in nulls else v for v in new_value)
                else:
                    old_value.append(None if new_value in nulls else new_value)
                new_value = old_value
            ret[param_name] = new_value
        return ret

    def get(self, request: HttpRequest):
        """Process a GET request.
        All parameters that accept multiple values can be input by either
        specifying the parameter more than once, or by typing commas or spaces as value
        separator. All parameter values are returned as string except the string
        'null' that will be converted to None
        """
        return self.response(data=self.parse_query_dict(request.GET))

    def post(self, request: HttpRequest):
        """Process a POST request"""
        if request.FILES:
            if not issubclass(self.formclass, FlatfileForm):
                return error_response("The given URL does not support "
                                      "uploaded files", self.CLIENT_ERR_CODE)
            return self.response(data=self.parse_query_dict(request.POST),
                                 files=request.FILES)
        else:
            stream = StringIO(request.body.decode('utf-8'))
            inputdict = yaml.safe_load(stream)
            return self.response(data=inputdict)

    def response(self, **form_kwargs):
        """process an input Response by calling `self.process` if the input is
        valid according to this class Form (`cls.formclass`). On error, return
        an appropriate JSON response

        :param form_kwargs: keyword arguments to be passed to this class Form
        """
        try:
            form = self.formclass(**form_kwargs)
            if not form.is_valid():
                err = form.errors_json_data()
                return error_response(err['message'], self.CLIENT_ERR_CODE,
                                      errors=err['errors'])

            response_data = form.response_data
            if form.data_format == form.DATA_FORMAT_CSV:
                return self.response_text(response_data)
            else:
                return self.response_json(response_data)
        except ValidationError as v_err:
            return error_response(v_err.message, self.CLIENT_ERR_CODE)
        except Exception as err:
            msg = f'Server error ({err.__class__.__name__}): {str(err)}'
            return error_response(msg, self.SERVER_ERR_CODE)

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
    urls = (f'{API_PATH}/trellis', f'{API_PATH}/model-model-comparison')


class ResidualsView(RESTAPIView):
    """EgsimQueryView subclass for generating Residuals plot responses"""

    formclass = ResidualsForm
    urls = (f'{API_PATH}/residuals', f'{API_PATH}/model-data-comparison')


class TestingView(RESTAPIView):
    """EgsimQueryView subclass for generating Testing responses"""

    formclass = TestingForm
    urls = (f'{API_PATH}/testing', f'{API_PATH}/model-data-testing')


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
