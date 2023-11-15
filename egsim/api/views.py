"""Module with the views for the web API (no GUI)"""
from http.client import responses
import re
from io import StringIO
from typing import Union, Type, Any

import yaml
from django.core.exceptions import ValidationError

from django.http import JsonResponse, HttpRequest, QueryDict
from django.http.response import HttpResponse
from django.views.generic.base import View
from django.forms.fields import MultipleChoiceField

from .forms.flatfile import FlatfileForm
from .forms.trellis import TrellisForm, ArrayField
from .forms.flatfile.gsim.residuals import ResidualsForm
from .forms.flatfile.gsim.testing import TestingForm
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

        multi_value_params = set()
        for field_name, field in form_cls.base_fields.items():
            if isinstance(field, (MultipleChoiceField, ArrayField)):
                multi_value_params.update(form_cls.param_names_of(field_name))

        ret = {}
        for param_name, values in querydict.lists():
            if param_name in multi_value_params:
                values = [None if v in nulls else v for val in values
                          for v in self.split_string(val)]
            else:
                values = [None if v in nulls else v for v in values]
                if len(values) == 1:
                    values = values[0]
            ret[param_name] = values
        return ret

    @staticmethod
    def split_string(string: str) -> list[str]:
        """
        :param string: a query-string value (e.g. '6' in '?param=6&...')
        :return: a list of chunks by comma-splitting the given string
        """
        _string = string.strip()
        if not _string:
            return []
        return re.split(r"\s*,\s*|\s+", _string)

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
            return self.response(data=yaml.safe_load(stream))

    def response(self, **form_kwargs):
        """process an input Response by calling `self.process` if the input is
        valid according to this class Form (`cls.formclass`). On error, return
        an appropriate JSON response

        :param form_kwargs: keyword arguments to be passed to this class Form
        """
        try:
            form = self.formclass(**form_kwargs)
            if not form.is_valid():
                return error_response(form.errors_json_data(), self.CLIENT_ERR_CODE)
            response_data, mime_type = form.response_data
            return self.create_response(response_data, mime_type)
        except ValidationError as v_err:
            return error_response(v_err, self.CLIENT_ERR_CODE)
        except NotImplementedError as ni_err:
            return error_response(ni_err, 501)
        except Exception as err:
            msg = f'Server error ({err.__class__.__name__}): {str(err)}'
            return error_response(msg, self.SERVER_ERR_CODE)

    @classmethod
    def create_response(cls, response_data: Any, content_type, **kwargs):
        return HttpResponse(response_data, content_type=content_type, **kwargs)


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


def error_response(content: Union[str, Exception, dict],
                   status_code=500, **kwargs) -> JsonResponse:
    """Convert the given exception, dict or string into a JSON
    response with content (or data or body) a dict with at least the key
    "message"
    (see https://google.github.io/styleguide/jsoncstyleguide.xml)

    :param content: dict, Exception or string. If dict, it will be used as response
        content (assuring there is at least the key 'message' which will be built
        from `status_code` if missing). If string a dict `{message: <content>}` will
        be built, if exception, the same dict will be returned but with 'message' built
        from the exception
    :param status_code: the response HTTP status code (int, default: 500)
    :param kwargs: optional params for JSONResponse (except 'content' and 'status')
    """
    if isinstance(content, dict):
        err_body = content
        err_body.setdefault('message', f'{status_code} ({responses[status_code]})')
    else:
        if isinstance(content, ValidationError):
            message = "; ".join(content.messages)
        else:
            message = str(content)
        err_body = {'message': message}
    return JsonResponse(err_body, safe=False, status=status_code, **kwargs)
