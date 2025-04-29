"""Module with the views for the web API (no GUI)"""
from __future__ import annotations
from collections.abc import Callable, Iterable
from datetime import date, datetime
import re
from io import StringIO, BytesIO
from typing import Union, Type, Optional, IO, Any
from urllib.parse import quote as urlquote

import yaml
import pandas as pd
from django.http import (JsonResponse, HttpRequest, QueryDict, FileResponse,
                         HttpResponseBase)
from django.http.response import HttpResponse
from django.views.generic.base import View

from egsim.smtk.converters import dataframe2dict
from egsim.smtk.validation import ModelError
from egsim.smtk.flatfile import FlatfileError, MissingColumnError
from .forms import APIForm, EgsimBaseForm, GsimInfoForm
from .forms.scenarios import PredictionsForm
from .forms.residuals import ResidualsForm


class MimeType:  # noqa
    """A collection of supported mime types (content_type in Django Response),
    loosely copied from mimetypes.types_map
    (https://docs.python.org/stable/library/mimetypes.html)
    """
    # IMPORTANT: avoid Enums or alike, attributes below will be passed as arg
    # `content_type` to build Responses and must be pure str (subclasses NOT allowed!)
    csv = "text/csv"
    json = "application/json"
    hdf = "application/x-hdf"
    png = "image/png"
    pdf = "application/pdf"
    svg = "image/svg+xml"
    # GZIP = "application/gzip"


class EgsimView(View):
    """Base View class for serving eGSIM HttpResponse. All views should inherits from this 
    class. Instance of this class handle GET and POST requests by parsing 
    request data and calling the abstract-like method `response`. Any exception raised 
    during the process will be caught and returned as 500 HttpResponse with the exception 
    string in the response body / content.
    
    Usage
    =====
    
    Simply implement the abstract-like method `response`:
    ```
    class MyEgsimView(EgsimView):
    
        def response(self, request: HttpRequest, data: dict, files: Optional[dict] = None) -> HttpResponseBase:
            content = ... # bytes or string sequence (serialized from a Python object)
            return HttpResponse(content, content_type=MimeType.csv, ...)
            # or, if cotent is a JSON dict:
            return JsonResponse(content)
    ```
    And then bind as usual this class view to an endpoint in `urls.py`, .e.g.:
    ```
    urlpatterns = [
        ...
        re_path(...endpoint..., MyEgsimView.as_view()),
        ...
    ]
    ```
    """  # noqa
    # error codes for general client and server errors:
    CLIENT_ERR_CODE, SERVER_ERR_CODE = 400, 500

    def get(self, request: HttpRequest) -> HttpResponseBase:
        """Process a GET request and return a Django Response"""
        try:
            return self.response(request, data=self.parse_query_dict(request.GET))
        except Exception as exc:
            return self.handle_exception(exc, request)

    def post(self, request: HttpRequest) -> HttpResponseBase:
        """Process a POST request and return a Django Response"""
        try:
            if request.FILES:
                # request.content_type='multipart/form-data' (see link below for details)
                # https://docs.djangoproject.com/en/stable/ref/request-response/#django.http.HttpRequest.FILES  # noqa
                return self.response(request,
                                     data=self.parse_query_dict(request.POST),
                                     files=request.FILES)
            else:
                # request.content_type might be anything (most likely
                # 'application/json' or 'application/x-www-form-urlencoded')
                data = request.POST
                if data:  # the request contains form data
                    return self.response(request, data=self.parse_query_dict(data))
                # not form data, so assume we have JSON (stored in request.body):
                data = StringIO(request.body.decode('utf-8'))
                return self.response(request, data=yaml.safe_load(data))
        except Exception as exc:
            return self.handle_exception(exc, request)

    def response(self,
                 request: HttpRequest,
                 data: dict,
                 files: Optional[dict] = None) -> HttpResponseBase:
        """Return a Django HttpResponse from the given arguments extracted from a GET
        or POST request. Any Exception raised here will be returned as 500 HttpResponse
        with `str(exception)` as Response body / content. Other specific error responses
        need to be returned in try except clauses, as usual:
        ```
        try:
            ...
        except ValueError as exc:
            return self.error_response(exc, status=400)
        ```

        :param request: the original HttpRequest
        :param data: the data extracted from the given request
        :param files: the files extracted from the given request, or None
        """
        raise NotImplementedError()

    def handle_exception(self, exc: Exception, request) -> HttpResponse:  # noqa
        """
        Handles any exception raised in `self.get` or `self.post` returning a
        server error (HttpResponse 500) with the exception string representation
        as response body / content
        """
        return self.error_response((
                f'Server error ({exc.__class__.__name__}): {exc}'.strip() +
                f'. Please contact the server administrator '
                f'if you think this error is due to a code bug'
        ), status=self.SERVER_ERR_CODE)

    def error_response(self,
                       message: Union[str, Exception, bytes] = '',
                       **kwargs) -> HttpResponse:
        """
        Return a HttpResponse with default status set to self.CLIENT_ERR_CODE
        and custom message in the response body / content. For custom status,
        provide the `status` explicitly as keyword argument
        """
        kwargs.setdefault('status', self.CLIENT_ERR_CODE)
        if not isinstance(message, (str, bytes)):
            message = str(message)
        return HttpResponse(message, **kwargs)

    def parse_query_dict(  # noqa
            self,
            query_dict: QueryDict, *,
            nulls=("null",),
            literal_comma: Optional[set] = frozenset()
    ) -> dict[str, Union[str, list[str]]]:
        """parse the given query dict and returns a Python dict. This method parses
        GET and POST request data and can be overwritten in subclasses.

        :param query_dict: a QueryDict resulting from an `HttpRequest.POST` or
            `HttpRequest.GET`, with percent-encoded characters already decoded
        :param nulls: tuple/list/set of strings to be converted to None. Defaults
            to `("null", )`
        :param literal_comma: set (defaults to empty set) of the parameter names for
            which "," in the value has to be treated as a normal character (By default,
            a comma acts as multi-value separator)
        """
        ret = {}
        for param_name, values in query_dict.lists():
            if param_name not in literal_comma and any(',' in v for v in values):
                values = [v for val in values for v in re.split(r"\s*,\s*|\s+", val)]
            for i in range(len(values)):
                if values[i] in nulls:
                    values[i] = None
            ret[param_name] = values[0] if len(values) == 1 else values

        return ret


class NotFound(EgsimView):
    """View for the 404 Not Found HttpResponse"""

    def response(self,
                 request: HttpRequest,
                 data: dict,
                 files: Optional[dict] = None) -> HttpResponse:
        return self.error_response(status=404)


class APIFormView(EgsimView):
    """:class:`EgsimView` subclass serving :class:`ApiForm` outputs. This class is an 
    EgsimView that additonally handles Form validation errors, returning a 400 
    HttpResponse with the error message in the response body / content.

    Usage
    =====
    
    Given an `APiForm` subclass named `MyApiForm`:
    
    Simple case: `MyApiForm.output()` method returns a JSON dict and your view is 
    supposed to return MimeType.json ("application/json") content only. You only need to
    implement a new endpoint in `urls.py`:
    
    ```
    urlpatterns = [
        ...
        re_path(...endpoint..., APIFormView.as_view(formclass=form)),
        ...
    ]
    ```

    Advanced case: create a new :class:`APIFormView` which, during the processing of a 
    request, reads the request's body 'format' parameter (default if missing 'json') 
    redirecting to the relative `response` method, and returning a 400 HttpResponse 
    error if no method is implemented). Implementation example:
    ```
    class MyApiFormView(APIFormView):

        formclass = MyApiForm  # bind this view to the given ApiForm **class**
        
        # for any desired format (see :class:`MimeType`) implement the relative 
        # `response_[format]` method returning the relative HttpResponse (see also
        # `self.response_json`, already implemented for all subclasses). Example (hdf):

        def response_hdf(self, form_output: Any, form: APIForm, **kwargs) -> HttpResponse:
            # Form is valid. First serialize `form_output`, e.g. as bytes:
            s_output = ... 
            # and then implement the HttpResponse from the given form output:
            return HttpResponse(s_output, content_type=MimeType.hdf, ...)
    ```
    Finally, bind as usual this class view to an endpoint in `urls.py`, .e.g.:
    ```
    urlpatterns = [
        ...
        re_path(...endpoint..., MyApiFormView.as_view()),
        ...
    ]
    ```
    """  # noqa
    # The APIForm of this view, to be set in subclasses:
    formclass: Type[APIForm] = None

    def response(self,
                 request: HttpRequest,
                 data: dict,
                 files: Optional[dict] = None):
        """Return a HttpResponse from the given arguments. The Response body / content
        will be populated with the output of this class Form
        (`self.formclass(...).output()`) serialized into the appropriate bytes sequence
        according to the 'format' parameter in 'data'.
        """
        rformat = data.pop('format', 'json')
        try:
            response_function = self.supported_formats()[rformat]
        except KeyError:
            return self.error_response(f'format: {EgsimBaseForm.ErrMsg.invalid}')

        form = self.formclass(data, files)
        if form.is_valid():
            return response_function(self, form.output(), form)  # noqa
        return self.error_response(form.errors_json_data()['message'])

    @classmethod
    def supported_formats(cls) -> \
            dict[str, Callable[[APIForm, APIForm], HttpResponse]]:
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


class GsimInfoView(APIFormView):
    """ApiFormView subclass for getting ground shaking model(s) info"""

    formclass = GsimInfoForm


class SmtkView(APIFormView):
    """APIFormView for smtk (strong motion toolkit) output (e.g. Predictions or
    Residuals, set in the `formclass` class attribute"""

    def response(self,
                 request: HttpRequest,
                 data: dict,
                 files: Optional[dict] = None):
        """Calls superclass method but catch ModelError(s) returning the appropriate
        HTTPResponse (Client error)"""
        try:
            return super().response(request=request, data=data, files=files)
        except MissingColumnError as mce:
            return self.error_response(f'flatfile: missing column(s) {str(mce)}')
        except FlatfileError as err:
            return self.error_response(f"flatfile: {str(err)}")
        except ModelError as m_err:
            return self.error_response(m_err)
        # any other exception will be handled in self.get and self.post and returned as
        # 5xx response

    def response_csv(  # noqa
            self, form_output: pd.DataFrame, form: APIForm, **kwargs  # noqa
    ) -> FileResponse:
        content = write_df_to_csv_stream(form_output)
        content.seek(0)  # for safety
        kwargs.setdefault('content_type', MimeType.csv)
        kwargs.setdefault('status', 200)
        return FileResponse(content, **kwargs)

    def response_hdf(  # noqa
            self, form_output: pd.DataFrame, form: APIForm, **kwargs  # noqa
    ) -> FileResponse:
        content = write_df_to_hdf_stream({'egsim': form_output})
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
        """Return a JSON response. This method is overwritten because the dataframe to
        JSON conversion differs if we computed measures of fit (param. `ranking=True`)
        """
        orient = 'dict' if form.cleaned_data['ranking'] else 'list'
        json_data = dataframe2dict(form_output, as_json=True,
                                   drop_empty_levels=True, orient=orient)
        kwargs.setdefault('status', 200)
        return JsonResponse(json_data, **kwargs)


# functions to read from BytesIO:
# (https://github.com/pandas-dev/pandas/issues/9246#issuecomment-74041497):


def write_df_to_hdf_stream(frames: dict[str, pd.DataFrame], **kwargs) -> BytesIO:
    """Write pandas DataFrame(s) to a HDF BytesIO"""
    if any(k == 'table' for k in frames.keys()):
        raise ValueError('Key "table" invalid (https://stackoverflow.com/a/70467886)')
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


def read_df_from_hdf_stream(stream: Union[bytes, IO], **kwargs) -> pd.DataFrame:
    """Read pandas DataFrame from an HDF BytesIO or bytes sequence

    :param stream: the stream / file-like (e.g. open file content)
    :param kwargs: additional arguments to be passed to pandas `read_hdf`
    """
    content = stream if isinstance(stream, bytes) else stream.read()
    # https://www.pytables.org/cookbook/inmemory_hdf5_files.html
    with pd.HDFStore(
            "data.h5",  # apparently unused for in-memory data
            mode="r",
            driver="H5FD_CORE",  # create in-memory file
            driver_core_backing_store=0,  # for safety, just in case
            driver_core_image=content) as store:
        return pd.read_hdf(store, **kwargs)  # noqa


def write_df_to_csv_stream(data: pd.DataFrame, **csv_kwargs) -> BytesIO:
    """Write pandas DataFrame to a CSV BytesIO"""
    content = BytesIO()
    data.to_csv(content, **csv_kwargs)  # noqa
    return content


def read_df_from_csv_stream(stream: Union[bytes, IO], **kwargs) -> pd.DataFrame:
    """
    Read pandas DataFrame from a CSV BytesIO or bytes sequence

    :param stream: the stream / file-like (e.g. open file content)
    :param kwargs: additional keyword arguments to be passed to pandas `read_csv`.
        NOTE the following keyword arguments WILL BE SET BY DEFAULT if not given:
        header=[0] (the first row contain the dataframe columns.
                    Pass a list (e.g. [0, 1, 2]) for multi-level header)
        index_col=0 (the first column is the dataframe index)
    """
    content = BytesIO(stream) if isinstance(stream, bytes) else stream
    header = kwargs.setdefault('header', [0])
    kwargs.setdefault('index_col', 0)
    dframe = pd.read_csv(content, **kwargs)
    if header and len(header) > 1:  # multi-index, in case of "Unnamed:" column, replace:
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
    https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/encodeURIComponent#description
    
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
