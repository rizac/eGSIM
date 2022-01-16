"""
Created on 17 Jan 2018

@author: riccardo
"""
import os
from io import StringIO
from os.path import join, dirname
import json
import yaml
from django.http import JsonResponse

from django.http.response import HttpResponse
from django.shortcuts import render
from django.conf import settings
from django.views.decorators.clickjacking import xframe_options_sameorigin

from . import figutils, TAB
from .frontend import get_context
from ..api.forms.model_from_region.model_from_region import ModelFromRegionForm
from ..api.forms.tools import describe, serialize
from ..api.models import FlatfileColumn
from ..api.views import error_response, QUERY_PARAMS_SAFE_CHARS, RESTAPIView


# common parameters to be passed to any Django template:
COMMON_PARAMS = {
    'project_name': 'eGSIM',
    # 'debug': settings.DEBUG,
    'data_protection_url': 'https://www.gfz-potsdam.de/en/data-protection/'
}


def main(request, selected_menu=None):
    """view for the main page"""
    context = COMMON_PARAMS | get_context(selected_menu, settings.DEBUG)
    return render(request, 'egsim.html', context)


@xframe_options_sameorigin
def home(request):
    """view for the home page (iframe in browser)"""
    egsim_data = {
        _.name: {'title': _.title, 'icon': _.icon} for _ in TAB
        if _ not in (TAB.apidoc,)
    }
    return render(request, 'home.html', dict(COMMON_PARAMS,
                                             debug=settings.DEBUG,
                                             egsim_data=egsim_data,
                                             info_str=('Version 2.0.0, '
                                                       'last updated: '
                                                       'January 2022')))


@xframe_options_sameorigin
def apidoc(request):
    """view for the home page (iframe in browser)"""
    filename = 'apidoc.html'
    # baseurl is the base URL for the services explained in the tutorial
    # It is the request.META['HTTP_HOST'] key. But during testing, this
    # key is not present. Actually, just use a string for the moment:
    baseurl = "<eGSIMsite>"
    # Note that the keus of the egsim_data dict below should NOT
    # be changed: if you do, you should also change the templates
    egsim_data = {
        # 'GSIMS': {
        #     'title': TITLES.GSIMS,
        #     'path': URLS.GSIMS_RESTAPI,
        #     'form': to_help_dict(GsimsView.formclass()),
        #     'key': KEY.GSIMS
        # },
        'trellis': {
            'title': TAB.trellis.title,
            'path': " or ".join(TAB.trellis.urls),
            'form': describe.as_dict(TAB.trellis.formclass),
            'key': TAB.trellis.name
        },
        'residuals': {
            'title': TAB.residuals.title,
            'path': " or ".join(TAB.residuals.urls),
            'form': describe.as_dict(TAB.residuals.formclass),
            'key': TAB.residuals.name
        },
        'testing': {
            'title': TAB.testing.title,
            'path': " or ".join(TAB.testing.urls),
            'form': describe.as_dict(TAB.testing.formclass),
            'key': TAB.testing.name
        },
        # 'FORMAT': {
        #     'form': to_help_dict(FormatForm())
        # }
    }

    # add references:
    with open(join(dirname(__file__), 'references.yaml')) as _:
        dic = yaml.safe_load(_)

    egsim_data['REFERENCES'] = dic

    return render(request, filename,
                  dict(COMMON_PARAMS,
                       debug=settings.DEBUG,
                       query_params_safe_chars=QUERY_PARAMS_SAFE_CHARS,
                       egsim_data=egsim_data,
                       baseurl=baseurl,
                       gmt=_get_flatfile_column_desc(),
                       )
                  )


def _get_flatfile_column_desc(as_html=True):
    ret = {}
    for ff_field in FlatfileColumn.objects.all():
        name = ff_field.name
        props = ff_field.properties
        dtype = props['dtype']
        if isinstance(dtype, (list, tuple)):
            type2str = 'categorical. Possible values:\n' + \
                       "\n".join(str(_) for _ in dtype)
        else:
            type2str = str(dtype)
        default = str(props.get('default', ''))
        if as_html:
            type2str = "<span style='white-space: nowrap'>%s</span>" % \
                type2str.replace('\n', '<br>')
        ret[name] = (type2str, default)
    return ret


@xframe_options_sameorigin
def imprint(request):
    return render(request, 'imprint.html', {
        'data_protection_url': COMMON_PARAMS['data_protection_url']
    })


def download_request(request, key: TAB, filename: str):
    """Return the request (configuration) re-formatted according to the syntax
    inferred from filename (*.json or *.yaml) to be downloaded by the front
    end GUI.

    :param key: a :class:`TAB` name associated to a REST API TAB (i.e.,
        with an associated Form class)
    """
    form_class = TAB[key].formclass
    input_dict = yaml.safe_load(StringIO(request.body.decode('utf-8')))
    form = form_class(data=input_dict)
    if not form.is_valid():
        errs = form.validation_errors()
        return error_response(errs['message'], RESTAPIView.CLIENT_ERR_CODE,
                              errors=errs['errors'])
    ext_nodot = os.path.splitext(filename)[1][1:].lower()
    buffer = serialize.as_text(input_dict, form_class, syntax=ext_nodot)
    if ext_nodot == 'json':
        # in the frontend the axios library expects bytes data (blob)
        # or bytes strings in order for the data to be correctly saved. Thus,
        # use text/javascript as 'application/json' does not work (or should we
        # better text/plain?)
        response = HttpResponse(buffer, content_type='text/javascript')
    else:
        response = HttpResponse(buffer, content_type='application/x-yaml')
    response['Content-Disposition'] = 'attachment; filename=%s' % filename
    return response


def download_response(request, key: TAB, filename: str):
    basename, ext = os.path.splitext(filename)
    if ext == '.csv':
        return download_ascsv(request, key, filename)
    elif ext == '.csv_eu':
        return download_ascsv(request, key, basename + '.csv', ';', ',')
    else:
        try:
            return download_asimage(request, filename)
        except KeyError:  # image format not found
            pass
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
    'eps': 'application/postscript',
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
    bytestr = figutils.get_img(data, layout, width, height, img_format)
    response = HttpResponse(bytestr, content_type=content_type)
    response['Content-Disposition'] = \
        'attachment; filename=%s' % filename
    response['Content-Length'] = len(bytestr)
    return response


def get_gsims_from_region(request):
    jsondata = json.loads(request.body.decode('utf-8'))
    form = ModelFromRegionForm(jsondata)
    if not form.is_valid():
        return JsonResponse(form.validation_errors())
    else:
        return JsonResponse(form.response_data)


def _test_err(request):
    """Dummy function raising for front end test purposes. Might be removed
    soon"""
    raise ValueError('this is a test error!')
