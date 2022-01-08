"""
Created on 17 Jan 2018

@author: riccardo
"""
import os
from io import StringIO
from os.path import join, dirname
import json
import yaml

from django.http.response import HttpResponse
from django.shortcuts import render
from django.conf import settings
from django.views.decorators.clickjacking import xframe_options_sameorigin

from . import figutils, TABS
from .vuejs import get_context
from ..api.forms.tools import describe, serialize
from ..api.models import FlatfileColumn
from ..api.views import error_response, QUERY_PARAMS_SAFE_CHARS


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
        _.name: {'title': _.title, 'icon': _.icon} for _ in TABS
        if _ not in (TABS.apidoc,)
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
            'title': TABS.trellis.title,
            'path': " or ".join(TABS.trellis.viewclass.urls),
            'form': describe.as_dict(TABS.trellis.formclass()),
            'key': TABS.trellis.name
        },
        'residuals': {
            'title': TABS.residuals.title,
            'path': " or ".join(TABS.residuals.viewclass.urls),
            'form': describe.as_dict(TABS.residuals.formclass()),
            'key': TABS.residuals.name
        },
        'testing': {
            'title': TABS.testing.title,
            'path': " or ".join(TABS.testing.viewclass.urls),
            'form': describe.as_dict(TABS.testing.formclass()),
            'key': TABS.testing.name
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


def download_request(request, tab_name, filename):
    """Return the request (configuration) re-formatted according to the syntax
    inferred from filename (*.json or *.yaml) to be downloaded by the front
    end GUI.

    :param tab_name: a :class:`TAB` name associated to a REST API TAB (i.e.,
        with an associated Form class)
    """
    form_class = TABS[tab_name].formclass
    input_dict = yaml.safe_load(StringIO(request.body.decode('utf-8')))
    form = form_class(data=input_dict)  # pylint: disable=not-callable
    if not form.is_valid():
        errs = form.validation_errors()
        return error_response(errs['message'], errs['code'],
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


def download_ascsv(request, tab_name, filename, sep=',', dec='.'):
    """Return the processed data as text/CSV. This method is used from within
    the browser when users want to get processed data as text/csv: as the
    browser stores the processed data dict, we just need to convert it as
    text/CSV.
    Consequently, the request's body is the JSON data resulting from a previous
    call of the GET or POST method of any REST API View.

    :param tab_name: a :class:`TAB` name associated to a REST API TAB (i.e.,
    with an associated Form class)
    """
    formclass = TABS[tab_name].formclass
    inputdict = yaml.safe_load(StringIO(request.body.decode('utf-8')))
    response = formclass.processed_data_as_csv(inputdict, sep, dec)
    response['Content-Disposition'] = 'attachment; filename=%s' % filename
    return response


def download_asimage(request, filename):
    """Return the image from the given request built in the frontend GUI
    according to the choosen plots
    """
    format = os.path.splitext(filename)[1][1:]  # @ReservedAssignment
    jsondata = json.loads(request.body.decode('utf-8'))
    data, layout, width, height = (jsondata['data'],
                                   jsondata['layout'],
                                   jsondata['width'],
                                   jsondata['height'])
    bytestr = figutils.get_img(data, layout, width, height, format)

    if format == 'eps':
        response = HttpResponse(bytestr, content_type='application/postscript')
    elif format == 'pdf':
        response = HttpResponse(bytestr, content_type='application/pdf')
    elif format == 'svg':
        response = HttpResponse(bytestr, content_type='image/svg+xml')
    else:
        response = HttpResponse(bytestr, content_type='image/png')
    response['Content-Disposition'] = \
        'attachment; filename=%s' % filename
    response['Content-Length'] = len(bytestr)
    return response


def _test_err(request):
    """Dummy function raising for front end test purposes. Might be removed
    soon"""
    raise ValueError('this is a test error!')
