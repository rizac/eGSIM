"""Module with the views for the web API (no GUI)"""
from __future__ import annotations
from collections.abc import Callable, Iterable
from http.client import responses
from datetime import date, datetime
import re
from io import StringIO, BytesIO
from typing import Union, Type, Optional, IO, Any
from urllib.parse import quote as urlquote

import yaml
import pandas as pd
from django.http import (JsonResponse, HttpRequest, QueryDict, FileResponse)
from django.http.response import HttpResponse
from django.views.generic.base import View
from django.forms.fields import MultipleChoiceField

from ..smtk.converters import dataframe2dict
from .forms import APIForm, EgsimBaseForm
from .forms.scenarios import PredictionsForm, ArrayField
from .forms.flatfile import FlatfileForm
from .forms.residuals import ResidualsForm


class MimeType:  # noqa
    """A collection of supported mime types (content_type in Django Response),
    loosely copied from mimetypes.types_map
    (https://docs.python.org/stable/library/mimetypes.html)
    """
    # NOTE: avoid Enums or alike, attributes below will be passed as arg `content_type`
    # to build Responses and must be pure str (subclasses NOT allowed!)
    csv = "text/csv"
    json = "application/json"
    hdf = "application/x-hdf"
    png = "image/png"
    pdf = "application/pdf"
    svg = "image/svg+xml"
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
    # error codes for general client and server errors:
    CLIENT_ERR_CODE, SERVER_ERR_CODE = 400, 500

    def parse_query_dict(self, querydict: QueryDict, nulls=("null",)) \
            -> dict[str, Union[str, list[str]]]:
        """parse the given query dict and returns a Python dict

        :param querydict: a QueryDict resulting from an `HttpRequest.POST` or
            `HttpRequest.GET`, with percent-encoded characters already decoded
        :param nulls: tuple/list/set of strings to be converted to None. Defaults
            to `("null", )`
        """
        form_cls = self.formclass

        default_multi_value_fields = {'gsim', 'imt', 'regionalization'}
        multi_value_params = set()
        for field_name, field in form_cls.base_fields.items():
            if field_name in default_multi_value_fields or \
                    isinstance(field, (MultipleChoiceField, ArrayField)):
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
        """Process a GET request and return a Django Response.
        All parameters that accept multiple values can be input by either
        specifying the parameter more than once, or by typing commas or spaces as value
        separator. All parameter values are returned as string except the string
        'null' that will be converted to None
        """
        return self.response(data=self.parse_query_dict(request.GET))

    def post(self, request: HttpRequest):
        """Process a POST request and return a Django Response"""
        if request.FILES:
            if not issubclass(self.formclass, FlatfileForm):
                return error_response("The given URL does not support "
                                      "uploaded files", self.CLIENT_ERR_CODE)
            # requests.FILE: https://docs.djangoproject.com/en/dev/ref/request-response/#django.http.HttpRequest.FILES  # noqa
            return self.response(data=self.parse_query_dict(request.POST),
                                 files=request.FILES)
        else:
            stream = StringIO(request.body.decode('utf-8'))
            return self.response(data=yaml.safe_load(stream))

    def response(self, **form_kwargs):
        """Return a Django Response from the given arguments. This method first creates
        a APIForm (from `self.formclass`) and puts the Form `output` into the
        returned Response body (or Response.content). On error, return
        an appropriate JSON response

        :param form_kwargs: keyword arguments to be passed to this class Form
        """
        try:
            rformat = form_kwargs['data'].pop('format', 'json')
            try:
                response_function = self.supported_formats()[rformat]
            except KeyError:
                return error_response(
                    f'format: {EgsimBaseForm.ErrMsg.invalid.value}',
                    self.CLIENT_ERR_CODE
                )
            form = self.formclass(**form_kwargs)
            if form.is_valid():
                obj = form.output()
                if form.is_valid():
                    return response_function(self, obj, form)  # noqa
            return error_response(form.errors_json_data(), self.CLIENT_ERR_CODE)
        except Exception as server_err:
            msg = (
                f'Server error ({server_err.__class__.__name__})' +
                ("" if not str(server_err) else str(server_err)) +
                f'. Please contact the server administrator '
                f'if you think this error is due to a code bug'
            )
            return error_response(msg, self.SERVER_ERR_CODE)

    @classmethod
    def supported_formats(cls) -> \
            dict[str, Callable[[RESTAPIView, APIForm], HttpResponse]]:
        """Return a list of supported formats (content_types) by inspecting
        this class implemented methods. Each dict key is a MimeType attr name,
        mapped to a class method used to obtain the response data in that
        mime type"""
        formats = {}
        for a in dir(cls):
            if a.startswith('response_'):
                meth = getattr(cls, a)
                if callable(meth):
                    frmt = a.split('_', 1)[1]
                    if hasattr(MimeType, frmt):
                        formats[frmt] = meth
        return formats

    def response_json(self, form_output: Any, form: APIForm, **kwargs) -> JsonResponse:
        kwargs.setdefault('status', 200)
        return JsonResponse(form_output, **kwargs)


class SmtkView(RESTAPIView):
    """RESTAPIView for smtk (strong motion toolkit) output (e.g. Predictions or
    Residuals, set in the `formclass` class attribute"""

    def response_csv(self, form_output: pd.DataFrame, form: APIForm, **kwargs)\
            -> FileResponse:  # noqa
        content = write_csv_to_buffer(form_output)
        content.seek(0)  # for safety
        kwargs.setdefault('content_type', MimeType.csv)
        kwargs.setdefault('status', 200)
        return FileResponse(content, **kwargs)

    def response_hdf(self, form_output: pd.DataFrame, form: APIForm, **kwargs)\
            -> FileResponse:  # noqa
        content = write_hdf_to_buffer({'egsim': form_output})
        content.seek(0)  # for safety
        kwargs.setdefault('content_type', MimeType.hdf)
        kwargs.setdefault('status', 200)
        return FileResponse(content, **kwargs)

    def response_json(self, form_output: pd.DataFrame, form: APIForm, **kwargs) \
            -> JsonResponse:
        """Return a JSON response. This method is implemented for
        legacy code/tests and should be avoided whenever possible"""
        json_data = dataframe2dict(form_output, as_json=True, drop_empty_levels=True)
        kwargs.setdefault('status', 200)
        return JsonResponse(json_data, **kwargs)


class PredictionsView(SmtkView):
    """SmtkView subclass for predictions computation"""

    formclass = PredictionsForm


class ResidualsView(SmtkView):
    """SmtkView subclass for residuals computation"""

    formclass = ResidualsForm

    def response_json(self, form_output: pd.DataFrame, form: APIForm, **kwargs) \
            -> JsonResponse:
        """Return a JSON response. This method is overwritten because the JSON
        data differs if we computed measures of fit (param. `ranking=True`) or not
        """
        orient = 'dict' if form.cleaned_data['ranking'] else 'list'
        json_data = dataframe2dict(form_output, as_json=True,
                                   drop_empty_levels=True, orient=orient)
        kwargs.setdefault('status', 200)
        return JsonResponse(json_data, **kwargs)


def error_response(error: Union[str, Exception, dict],
                   status=500, **kwargs) -> JsonResponse:
    """Return a JSON response from the given error. The response body/content will be
    a dict with (at least) the key 'message' (If missing, the key value will be
    inferred and added to the dict. The dict format is inspired from:
    https://google.github.io/styleguide/jsoncstyleguide.xml).

    :param error: dict, Exception or string:
        - If dict, JSONResponse.content = dict (if dict['message'] is missing,
          it will be set inferred from `status`).
        - If `str` or `Exception`, JSONResponse.content = {'message': str(error)}
    :param status: the response HTTP status code (int, default: 500)
    :param kwargs: optional params for JSONResponse (except 'content' and 'status')
    """
    if isinstance(error, dict):
        content = dict(error)
        content.setdefault('message', f'{responses[status]} (status code: {status})')
    else:
        content = {'message': str(error)}
    kwargs.setdefault('content_type', MimeType.json)
    return JsonResponse(content, status=status, **kwargs)


# functions to read from BytesIO:
# (https://github.com/pandas-dev/pandas/issues/9246#issuecomment-74041497):


def write_hdf_to_buffer(frames: dict[str, pd.DataFrame], **kwargs) -> BytesIO:
    """Write in HDF format to a BytesIO the passed DataFrame(s)"""
    with pd.HDFStore(
            "data.h5",  # apparently unused for in-memory data
            mode="w",
            driver="H5FD_CORE",  # create in-memory file
            driver_core_backing_store=0,  # prevent saving to file on close
            **kwargs) as out:
        for key, dfr in frames.items():
            out.put(key, dfr, format='table')
            # out[key] = df
        # https://www.pytables.org/cookbook/inmemory_hdf5_files.html
        return BytesIO(out._handle.get_file_image())  # noqa


def read_hdf_from_buffer(
        buffer: Union[bytes, IO], key: Optional[str] = None) -> pd.DataFrame:
    """Read from a BytesIO containing HDF data"""
    content = buffer if isinstance(buffer, bytes) else buffer.read()
    # https://www.pytables.org/cookbook/inmemory_hdf5_files.html
    with pd.HDFStore(
            "data.h5",  # apparently unused for in-memory data
            mode="r",
            driver="H5FD_CORE",  # create in-memory file
            driver_core_backing_store=0,  # for safety, just in case
            driver_core_image=content) as store:
        if key is None:
            keys = []
            for k in store.keys():
                if not any(k.startswith(_) for _ in keys):
                    keys.append(k)
                if len(keys) > 1:
                    break
            if len(keys) == 1:
                key = keys[0]
        # Note: top-level keys can be passed with or wothout leading slash:
        return store[key]


def write_csv_to_buffer(data: pd.DataFrame, **csv_kwargs) -> BytesIO:
    """Write in CSV format to a BytesIO the passed DataFrame(s)"""
    content = BytesIO()
    data.to_csv(content, **csv_kwargs)  # noqa
    return content


def read_csv_from_buffer(buffer: Union[bytes, IO],
                         header: Optional[Union[int, list[int]]] = None) -> pd.DataFrame:
    """
    Read from a file-like object containing CSV data. Do not supply header
    for buffer resulting from residuals/ predictions computation (3 header rows),
    pass 0 for rankings / measures of fit computation (1 header row).
    """
    content = BytesIO(buffer) if isinstance(buffer, bytes) else buffer
    if header is None:
        header = [0, 1, 2]
    dframe = pd.read_csv(content, header=header, index_col=0)
    dframe.rename(columns=lambda c: "" if c.startswith("Unnamed:") else c,
                  inplace=True)
    return dframe


# Default safe characters in `as_querystring`. Letters, digits are safe by default
# and don't need to be added. '_.-~' are safe but are added anyway for safety:
QUERY_STRING_SAFE_CHARS = "-_.~!*'()"


def as_querystring(
        data: Any,
        safe=QUERY_STRING_SAFE_CHARS,
        none_value='null',
        encoding: str = None,
        errors: str = None) -> str:
    """Return `data` as query string (URL portion after the '?' character) for GET
    requests. With the default set of input parameters, this function encodes strings
    exactly as JavaScript encodeURIComponent:
    https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/encodeURIComponent#description   # noqa
    Examples:
    ```
    as_querystring(' ') = "%20"
    as_querystring([1, 2]) = "1,2"
    as_querystring({'a': [1, 2], 'b': ' '}) = "a=1,2&b=%20"
    ```

    :param data: the data to be encoded. Containers (e.g. lists/tuple/dict) are
        allowed as long as they do not contain nested containers, because this
        would result in invalid URLs
    :param safe: string of safe characters that should not be encoded
    :param none_value: string to be used when encountering None (default 'null')
    :param encoding: used to deal with non-ASCII characters. See `urllib.parse.quote`
    :param errors: used to deal with non-ASCII characters. See `urllib.parse.quote`
    """  # noqa
    if data is None:
        return none_value
    if data is True or data is False:
        return str(data).lower()
    if isinstance(data, dict):
        return '&'.join(f'{f}={as_querystring(v)}' for f, v in data.items())
    if isinstance(data, Iterable) and not isinstance(data, (str, bytes)):
        return ','.join(f'{as_querystring(v)}' for v in data)

    if isinstance(data, (date, datetime)):
        data = data.isoformat(sep='T')
    elif not isinstance(data, (str, bytes)):
        data = str(data)
    return urlquote(data, safe=safe, encoding=encoding, errors=errors)
