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
from django.http import (
    JsonResponse,
    HttpRequest,
    QueryDict,
    FileResponse,
    HttpResponseBase
)
from django.http.response import HttpResponse
from django.views.generic.base import View

from egsim.smtk.converters import dataframe2dict
from egsim.smtk.validation import ModelError
from egsim.smtk.flatfile import FlatfileError, MissingColumnError
from .forms import APIForm, EgsimBaseForm, GsimInfoForm
from .forms.scenarios import PredictionsForm
from .forms.residuals import ResidualsForm


class MimeType:  # noqa
    """
    A collection of supported mime types (content_type in Django Response),
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
    """
    Base View class for serving eGSIM HttpResponse. All views should inherit from
    this class, implementing the abstract-like method `response` (**see docstring
    therein for details**). After that, you can map this view to a given URL as usual
    (in `urls.py`):
    ```
    urlpatterns = [
        ...
        re_path(<endpoint>, MyEgsimView.as_view()),
        ...
    ]
    ```
    """
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
                # <https://docs.djangoproject.com/en/stable/ref/request-response/#django.http.HttpRequest.FILES>
                return self.response(
                    request,
                    data=self.parse_query_dict(request.POST),
                    files=request.FILES
                )
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

    def response(
        self,
        request: HttpRequest,
        data: dict,
        files: Optional[dict] = None
    ) -> HttpResponseBase:
        """
        Return a Django HttpResponse from the given arguments extracted from a GET
        or POST request. Any Exception raised here will be returned as 500 HttpResponse
        with `str(exception)` as Response body / content. Other specific error responses
        need to be returned in try except clauses, as usual:
        ```
        try:
            content = ... # bytes or string sequence (serialized from a Python object)
            return HttpResponse(content, content_type=MimeType.csv, ...)
            # or, if content is a JSON dict:
            return JsonResponse(content)
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
        return error_response(
            f'Server error ({exc.__class__.__name__}): {str(exc).strip()}. '
            f'. Please contact the server administrator '
            f'if you think this error is due to a code bug',
            status=500
        )

    def parse_query_dict(  # noqa
        self,
        query_dict: QueryDict, *,
        nulls=("null",),
        literal_comma: Optional[set] = frozenset()
    ) -> dict[str, Union[str, list[str]]]:
        """
        Parse the given query dict and returns a Python dict. This method parses
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


def error_response(
    message: Union[str, Exception, bytes] = '',
    status=400,
    **kwargs
) -> HttpResponse:
    """
    Return a HttpResponse with default status 400 (client error)
    and custom message in the response body / content. For custom status,
    provide the `status` explicitly as keyword argument
    """
    if not isinstance(message, (str, bytes)):
        message = str(message)
    return HttpResponse(message, status=status, **kwargs)


class NotFound(EgsimView):
    """View for the 404 Not Found HttpResponse"""

    def response(
        self,
        request: HttpRequest,
        data: dict,
        files: Optional[dict] = None
    ) -> HttpResponse:
        return error_response(status=404)


class APIFormView(EgsimView):
    """
    :class:`EgsimView` subclass serving :class:`ApiForm.output()` objects and 
    expecting a 'format' request parameter (any attribute of :class:`MimeType`)
    dictating the response type. Form validation errors will be 
    returned as 400 HttpResponse, any uncaught exception as 500 HttpResponse.
    
    Usage
    =====
    
    Given an `APiForm` subclass named `MyApiForm`:
    
    1. If this view is supposed to return JSON data only and `MyApiForm.output()` 
    returns a JSON serializable dict, then simply implement a new endpoint in `urls.py`:
    
    ```
    urlpatterns = [
        ...
        re_path(...endpoint..., APIFormView.as_view(formclass=form)),
        ...
    ]
    ```

    2. In any other case, here a snippet to serve HDF data:
    
    ```
    class MyApiFormView(APIFormView):

        formclass = MyApiForm  # bind this view to the given ApiForm **class**
        
        responses: {
            'hdf': lambda form: MyApiFormView.response_hdf(form)
        }
        
        @staticmethod
        def response_hdf(form: APIForm) -> HttpResponse:
            s_output = ... serialize form.output() (into BytesIO probably) ...
            return HttpResponse(s_output, content_type=MimeType.hdf, status=200, ...)
    ```

    Finally, bind as usual this class view to an endpoint in `urls.py`, .e.g.:
    ```
    urlpatterns = [
        ...
        re_path(...endpoint..., MyApiFormView.as_view()),
        ...
    ]
    ```
    """
    # The APIForm of this view, to be set in subclasses:
    formclass: Type[APIForm] = None

    responses: dict[str, Callable[[APIForm], HttpResponseBase]] = {
        'json': lambda form: JsonResponse(form.output(), status=200)
    }

    def response(
        self,
        request: HttpRequest,
        data: dict,
        files: Optional[dict] = None
    ) -> HttpResponseBase:
        """
        Return a HttpResponse from the given arguments. The Response body / content
        will be populated with the output of this class Form
        (`self.formclass(...).output()`) serialized into the appropriate bytes sequence
        according to the 'format' parameter in 'data'.
        """
        rformat = data.pop('format', list(self.responses)[0])
        try:
            response_function = self.responses[rformat]
        except KeyError:
            return error_response(f'format: {EgsimBaseForm.ErrMsg.invalid}')

        form = self.formclass(data, files)
        if form.is_valid():
            return response_function(form)  # noqa
        return error_response(form.errors_json_data()['message'])


class GsimInfoView(APIFormView):
    """ApiFormView subclass for getting ground shaking model(s) info"""

    formclass = GsimInfoForm


class SmtkView(APIFormView):
    """
    APIFormView for strong motion toolkit (smtk) output, e.g., Predictions, Residuals.
    This view supported response formats are 'json', 'csv', 'hdf' (the default).
    Subclasses should in principle only implement the class attribute `formclass`
    """

    responses = {
        'hdf': lambda form: SmtkView.response_hdf(form),
        'csv': lambda form: SmtkView.response_csv(form)
    }

    def response(
        self,
        request: HttpRequest,
        data: dict,
        files: Optional[dict] = None
    ) -> HttpResponseBase:
        """
        Call superclass method but catch ModelError(s) returning the appropriate
        HTTPResponse (Client error)
        """
        try:
            return super().response(request=request, data=data, files=files)
        except MissingColumnError as mce:
            return error_response(f'flatfile: missing column(s) {str(mce)}')
        except FlatfileError as err:
            return error_response(f"flatfile: {str(err)}")
        except ModelError as m_err:
            return error_response(m_err)
        # any other exception will be handled in self.get and self.post and returned as
        # 5xx response

    @staticmethod
    def response_csv(form: APIForm) -> FileResponse:
        """Return CSV-data response. form is already validated"""

        content = write_df_to_csv_stream(form.output())
        content.seek(0)  # for safety
        return FileResponse(content, content_type=MimeType.csv, status=200)

    @staticmethod
    def response_hdf(form: APIForm) -> FileResponse:
        """Return CSV-data response. form is already validated"""

        content = write_df_to_hdf_stream({'egsim': form.output()})
        content.seek(0)  # for safety
        return FileResponse(content, content_type=MimeType.hdf, status=200)


class PredictionsView(SmtkView):
    """SmtkView subclass for predictions computation"""

    formclass = PredictionsForm

    responses = SmtkView.responses | {
        'json': lambda form: JsonResponse(
            dataframe2dict(form.output(), as_json=True, drop_empty_levels=True),
            status=200
        )
    }


class ResidualsView(SmtkView):
    """SmtkView subclass for residuals computation"""

    formclass = ResidualsForm

    responses = SmtkView.responses | {
        'json': lambda form: JsonResponse(
            dataframe2dict(
                form.output(),
                as_json=True,
                drop_empty_levels=True,
                orient='dict' if form.cleaned_data['ranking'] else 'list'
            ),
            status=200
        )
    }


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
        **kwargs
    ) as out:
        for key, dfr in frames.items():
            out.put(key, dfr, format='table')
            # out[key] = df
        # https://www.pytables.org/cookbook/inmemory_hdf5_files.html
        return BytesIO(out._handle.get_file_image())  # noqa


def read_df_from_hdf_stream(stream: Union[bytes, IO], **kwargs) -> pd.DataFrame:
    """
    Read pandas DataFrame from an HDF BytesIO or bytes sequence

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
        driver_core_image=content
    ) as store:
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
    errors: str = None
) -> str:
    """
    Return `data` as query string (URL portion after the '?' character) for GET
    requests. With the default set of input parameters, this function encodes strings
    exactly as JavaScript encodeURIComponent:
    <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/encodeURIComponent#description>
    
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
    """
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
