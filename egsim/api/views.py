"""Module with the views for the web API (no GUI)"""
from collections.abc import Callable
from enum import StrEnum
from http.client import responses
import re
from io import StringIO, BytesIO
from typing import Union, Type, Optional

import yaml
import pandas as pd
from django.core.exceptions import ValidationError

from django.http import (JsonResponse, HttpRequest, QueryDict,
                         StreamingHttpResponse)
from django.http.response import HttpResponse
from django.views.generic.base import View
from django.forms.fields import MultipleChoiceField

from .forms.flatfile import FlatfileForm
from .forms.trellis import TrellisForm, ArrayField
from .forms.flatfile.gsim.residuals import ResidualsForm
from .forms import APIForm
from ..smtk.converters import dataframe2dict


class MIMETYPE(StrEnum):  # noqa
    """An enum of supported mime types (content_type in Django Response) loosely
    copied from mimetypes.types_map (https://docs.python.org/3.8/library/mimetypes.html)
    """
    CSV = "text/csv"
    JSON = "application/json"
    HDF = "application/x-hdf"
    PNG = "image/png"
    PDF = "application/pdf"
    SVG = "image/svg+xml"
    # GZIP = "application/gzip"




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
            rformat = form_kwargs.pop('format', MIMETYPE.JSON.name.lower())
            try:
                mimetype = MIMETYPE[rformat]
                response_function = self.supported_formats()[mimetype]
            except KeyError:
                raise ValidationError(f'Invalid format {rformat}')
            form = self.formclass(**form_kwargs)
            if not form.is_valid():
                return error_response(form.errors_json_data(), self.CLIENT_ERR_CODE)
            cleaned_data = form.cleaned_data
            return response_function(cleaned_data)
        except (KeyError, ValidationError) as v_err:
            return error_response(v_err, self.CLIENT_ERR_CODE)
        except (KeyError, AttributeError, NotImplementedError) as ni_err:
            return error_response(ni_err, 501)
        except Exception as err:
            msg = f'Server error ({err.__class__.__name__}): {str(err)}'
            return error_response(msg, self.SERVER_ERR_CODE)

    @classmethod
    def supported_formats(cls) -> dict[MIMETYPE, Callable[[dict], HttpResponse]]:
        """Return a list of supported formats (content_types) by inspecting
        this class implemented methods. Each dict key is a MIMETYPE enum,
        mapped to this class method used to obtain the response data in that
        mime type"""
        formats = {}
        for a in dir(cls):
            if a.startswith('response_'):
                meth = getattr(cls, a)
                if callable(meth):
                    frmt = a.split('_', 1)[1]
                    try:
                        formats[MIMETYPE[frmt.upper()]] = meth
                    except KeyError:
                        pass
        return formats

    def response_json(self, cleaned_data:dict):
        return JsonResponse(self.formclass.response_data(cleaned_data))


# we need to provide the full URL of the views here, because the frontend need
# to inject those URLs (to call them when pressing OK buttons). So prefixes must
# be written here and not in `urls.py`:
API_PATH = 'query'


class TrellisView(RESTAPIView):
    """EgsimQueryView subclass for generating Trellis plots responses"""

    formclass = TrellisForm
    urls = (f'{API_PATH}/trellis', f'{API_PATH}/model-model-comparison')

    def response_csv(self, cleaned_data:dict):
        return pandas_response(self.formclass.response_data(cleaned_data), MIMETYPE.CSV)

    def response_hdf(self, cleaned_data:dict):
        return pandas_response(self.formclass.response_data(cleaned_data), MIMETYPE.HDF)

    def response_json(self, cleaned_data:dict):
        json_data = dataframe2dict(self.formclass.response_data(cleaned_data),
                                   as_json=True, drop_empty_levels=True)
        return JsonResponse(json_data)


class ResidualsView(RESTAPIView):
    """EgsimQueryView subclass for generating Residuals plot responses"""

    formclass = ResidualsForm
    urls = (f'{API_PATH}/residuals', f'{API_PATH}/model-data-comparison')

    def response_csv(self, cleaned_data:dict):
        return pandas_response(self.formclass.response_data(cleaned_data), MIMETYPE.CSV)

    def response_hdf(self, cleaned_data:dict):
        return pandas_response(self.formclass.response_data(cleaned_data), MIMETYPE.HDF)

    def response_json(self, cleaned_data:dict):
        json_data = dataframe2dict(self.formclass.response_data(cleaned_data),
                                   as_json=True, drop_empty_levels=True)
        return JsonResponse(json_data)


def error_response(error: Union[str, Exception, dict],
                   status=500, **kwargs) -> JsonResponse:
    """Returns a response (JSONResponse by default, unless a `content_type` is
    explicitly set in `kwargs`) from the given error. The response content will be
    inferred from error and will be a `dict` with at least the key "message" (mapped
    to a `str`).

    (see https://google.github.io/styleguide/jsoncstyleguide.xml)

    :param error: dict, Exception or string. If dict, it will be used as response
        content (assuring there is at least the key 'message' which will be built
        from `status_code` if missing). If string, a dict `{message: <content>}` will
        be built. If exception, the same dict but with the `message` key mapped to
        a string inferred from the exception
    :param status: the response HTTP status code (int, default: 500)
    :param kwargs: optional params for JSONResponse (except 'content' and 'status')
    """
    content = {}
    if isinstance(error, dict):
        content = error
        message = f'{status} {responses[status]}'
    else:
        if isinstance(error, ValidationError):
            message = "; ".join(error.messages)
        else:
            message = str(error)
    content.setdefault('message', message)
    kwargs.setdefault('content_type', MIMETYPE.JSON)
    return JsonResponse(content, status=status, **kwargs)


def pandas_response(data:pd.DataFrame, content_type:Optional[MIMETYPE]=None,
                    status=200, reason=None, headers=None, charset=None):
    """Return a `HTTPResponse` for serving pandas dataframes as either HDF or CSV

    :param content_type: optional content type. Either MIMETYPE.CSV or MIMETYPE.HDF
        If None, it defaults to the former.
    """
    if content_type in (None, MIMETYPE.CSV):
        content = BytesIO()
        data.to_csv(content)
        nbytes = content.getbuffer().nbytes
        content.seek(0)
        content_type = MIMETYPE.CSV
    elif content_type == MIMETYPE.HDF:
        content = write_hdf_to_buffer(egsim=data)
        nbytes = content.getbuffer().nbytes
        content.seek(0)
    else:
        return error_response(f'cannot serve {data.__class__.__name__} '
                              f'as type "{content_type}"', status=500)
    headers = headers or {}
    headers['Content-Length'] = nbytes
    return StreamingHttpResponse(content, status=status, content_type=content_type,
                                 reason=reason, headers=headers, charset=charset)


def write_hdf_to_buffer(**frames: pd.DataFrame):
    with pd.get_store(
            "data.h5", mode="w", driver="H5FD_CORE",
            driver_core_backing_store=0
            ) as out:
        for key, df in frames.items():
            out[key] = df
        return out._handle.get_file_image()
