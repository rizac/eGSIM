"""
Created on 17 Jan 2018

@author: riccardo
"""
import os
from os.path import join, dirname, abspath
from io import StringIO
import json
import yaml

from django.http.response import HttpResponse, JsonResponse
from django.shortcuts import render
from django.conf import settings
from django.views.decorators.clickjacking import xframe_options_sameorigin

from .templates.egsim import TAB, URLS, get_init_json_data
from .templates.apidoc import get_apidoc_page_renderer_context
from ..api.forms.flatfile.compilation import (FlatfileRequiredColumnsForm,
                                              FlatfileInspectionForm, FlatfilePlotForm)
from ..api.forms import GsimFromRegionForm
from ..api.views import error_response, RESTAPIView


def main(request, selected_menu=None):
    """view for the main page"""
    template = 'egsim.html'
    return render(request, template, context={'debug': settings.DEBUG})


def main_page_init_data(request):
    """JSON data requested by the browser app at startup to initialize the HTML page"""
    request_body = json.loads(request.body)
    browser = request_body.get('browser', {})
    selected_menu = request_body.get('selectedMenu', TAB.home.name)
    return JsonResponse(get_init_json_data(browser, selected_menu, settings.DEBUG))


@xframe_options_sameorigin
def home(request):
    """view for the home page (iframe in browser)"""
    template = 'info_pages/home.html'
    return render(request, template, context=_get_home_page_renderer_context())


def _get_home_page_renderer_context():
    return {'ref_and_license_url': URLS.REF_AND_LICENSE}


@xframe_options_sameorigin
def apidoc(request):
    """view for the home page (iframe in browser)"""
    template = 'info_pages/apidoc/base.html'
    context = {}  # get_apidoc_page_renderer_context(settings.DEBUG)
    return render(request, template, context=context)


@xframe_options_sameorigin
def ref_and_license(request):
    """view for the home page (iframe in browser)"""
    template = 'info_pages/ref_and_license.html'
    context = _get_ref_and_license_page_renderer_context()
    return render(request, template, context=context)


def _get_ref_and_license_page_renderer_context():
    refs = {}
    with open(join(dirname(dirname(abspath(__file__))), 'api',
                   'management', 'commands', 'data', 'data_sources.yaml')) as _:
        for ref in yaml.safe_load(_).values():
            name = ref.pop('display_name')
            refs[name] = ref
    return {'references': refs}


@xframe_options_sameorigin
def imprint(request):
    template = 'info_pages/imprint.html'
    return render(request, template, context=_get_imprint_page_renderer_context())


def _get_imprint_page_renderer_context():
    return {
        'data_protection_url': URLS.DATA_PROTECTION,
        'ref_and_license_url': URLS.REF_AND_LICENSE
    }


def download_request(request, key: TAB, filename: str):
    """Return the request (configuration) re-formatted according to the syntax
    inferred from filename (*.json or *.yaml) to be downloaded by the front
    end GUI.

    :param key: a :class:`TAB` name associated to a REST API TAB (i.e.,
        with an associated Form class)
    """
    form_class = TAB[key].formclass

    def input_dict() -> dict:
        """return the input dict. This function allows to work each time
        on a new copy of the input data"""
        return yaml.safe_load(StringIO(request.body.decode('utf-8')))

    form = form_class(data=input_dict())
    if not form.is_valid():
        errs = form.errors_json_data()
        return error_response(errs['message'], RESTAPIView.CLIENT_ERR_CODE,
                              errors=errs['errors'])
    ext_nodot = os.path.splitext(filename)[1][1:].lower()
    compact = True
    if ext_nodot == 'json':
        # in the frontend the axios library expects bytes data (blob)
        # or bytes strings in order for the data to be correctly saved. Thus,
        # use text/javascript because 'application/json' does not work (or should
        # we better use text/plain?)
        response = HttpResponse(StringIO(form.as_json(compact=compact)),
                                content_type='text/javascript')
    elif ext_nodot == 'querystring':
        response = HttpResponse(StringIO(form.as_querystring(compact=compact)),
                                content_type='text/plain')
    else:
        response = HttpResponse(StringIO(form.as_yaml(compact=compact)),
                                content_type='application/x-yaml')
    response['Content-Disposition'] = 'attachment; filename=%s' % filename
    return response


def download_response(request, key: TAB, filename: str):
    basename, ext = os.path.splitext(filename)
    if ext == '.csv':
        return download_ascsv(request, key, filename)
    elif ext == '.csv_eu':
        return download_ascsv(request, key, basename + '.csv', ';', ',')
    elif ext[1:] in _IMG_FORMATS:
        return download_asimage(request, filename)
    return error_response(f'Unsupported format "{ext[1:]}"', RESTAPIView.CLIENT_ERR_CODE)


def download_ascsv(request, key: TAB, filename: str, sep=',', dec='.'):
    """Return the processed data as text/CSV. This method is used from within
    the browser when users want to get processed data as text/csv: as the
    browser stores the processed data dict, we just need to convert it as
    text/CSV.
    Consequently, the request's body is the JSON data resulting from a previous
    call of the GET or POST method of any REST API View.

    :param key: a :class:`TAB` name associated to a REST API TAB (i.e.,
        with an associated Form class)
    """
    formclass = TAB[key].formclass
    inputdict = yaml.safe_load(StringIO(request.body.decode('utf-8')))
    response_data = formclass.to_csv_buffer(inputdict, sep, dec)
    response = TAB[key].viewclass.response_text(response_data)
    response['Content-Disposition'] = 'attachment; filename=%s' % filename
    return response


_IMG_FORMATS = {
    # 'eps': 'application/postscript',  # NA (note: requires poppler library in case)
    'pdf': 'application/pdf',
    'svg': 'image/svg+xml',
    'png': 'image/png'
}


def download_asimage(request, filename: str):
    """Return the image from the given request built in the frontend GUI
    according to the chosen plots
    """
    img_format = os.path.splitext(filename)[1][1:]
    content_type = _IMG_FORMATS[img_format]
    jsondata = json.loads(request.body.decode('utf-8'))
    data, layout, width, height = (jsondata['data'],
                                   jsondata['layout'],
                                   jsondata['width'],
                                   jsondata['height'])
    from plotly import graph_objects as go, io as pio
    fig = go.Figure(data=data, layout=layout)
    # fix for https://github.com/plotly/plotly.py/issues/3469:
    pio.full_figure_for_development(fig, warn=False)
    # compute bytes string:
    bytestr = fig.to_image(format=img_format, width=width, height=height, scale=5)  # , scale=2)
    response = HttpResponse(bytestr, content_type=content_type)
    response['Content-Disposition'] = \
        'attachment; filename=%s' % filename
    response['Content-Length'] = len(bytestr)
    return response


def get_gsims_from_region(request):
    return RESTAPIView.as_view(formclass=GsimFromRegionForm)(request)


def flatfile_required_columns(request):
    return RESTAPIView.as_view(formclass=FlatfileRequiredColumnsForm)(request)


def flatfile_inspection(request):
    return RESTAPIView.as_view(formclass=FlatfileInspectionForm)(request)


def flatfile_plot(request):
    return RESTAPIView.as_view(formclass=FlatfilePlotForm)(request)


def _test_err(request):
    """Dummy function raising for front end test purposes. Might be removed
    soon"""
    raise ValueError('this is a test error!')
