"""
Created on 17 Jan 2018

@author: riccardo
"""
import os
from io import StringIO
from os.path import join, dirname
import json
import yaml

from django.db.models import Prefetch, QuerySet
from django.http.response import HttpResponse
from django.shortcuts import render
from django.conf import settings

from . import figutils, guiutils, TABS, QUERY_PARAMS_SAFE_CHARS, error_response
from .guiutils import to_help_dict, dump_request_data
from ..api.models import Gsim, Imt


# common parameters to be passed to any Django template:
COMMON_PARAMS = {
    'project_name': 'eGSIM',
    # 'debug': settings.DEBUG,
    'data_protection_url': 'https://www.gfz-potsdam.de/en/data-protection/'
}


def query_gims() -> QuerySet:
    """Return a QuerySet of Gsims instances from the database, with the
    necessary information (field 'warning' and associated Imts in the `imtz`
    attribute)
    """
    # Try to perform everything in a single more efficient query. Use
    # prefetch_related for this. It Looks like we need to assign the imts to a
    # new attribute, the attribute "Gsim.imts" does not work as expected
    prefetch_imts = Prefetch('imts', queryset=Imt.objects.only('name'),
                             to_attr='imtz')

    return Gsim.objects.only('name', 'warning').prefetch_related(prefetch_imts)


def main(request, selected_menu=None):
    """view for the main page"""

    # Tab components (one per tab, one per activated vue component)
    # (key, label and icon) (the last is bootstrap fontawesome name)
    components_tabs = [[_.name, _.title, _.icon] for _ in TABS]

    # this can be changed if needed:
    sel_component = TABS.home.name if not selected_menu else selected_menu

    # setup browser detection
    allowed_browsers = [['Chrome', 49], ['Firefox', 45], ['Safari', 10]]
    allowed_browsers_msg = ', '.join('%s &ge; %d' % (brw, ver)
                                     for brw, ver in allowed_browsers)
    invalid_browser_message = ('Some functionalities might not work '
                               'correctly. In case, please use any of the '
                               'following tested browsers: %s' %
                               allowed_browsers_msg)

    gsims = {g.name: [[i.name for i in g.imtz], g.warning] for g in query_gims()}

    components_props = guiutils.get_components_properties(settings.DEBUG)

    context = {
        **COMMON_PARAMS,
        'debug': settings.DEBUG,
        'sel_component': sel_component,
        'components': components_tabs,
        'component_props': json.dumps(components_props),
        'gsims': gsims,
        'allowed_browsers': allowed_browsers,
        'invalid_browser_message': invalid_browser_message
    }
    return render(request, 'egsim.html', context)


def home(request):
    """view for the home page (iframe in browser)"""
    egsim_data = {
        _.name: {'title': _.title, 'icon': _.icon} for _ in TABS
        if TABS not in (TABS.doc,)
    }
    return render(request, 'home.html', dict(COMMON_PARAMS,
                                             debug=settings.DEBUG,
                                             egsim_data=egsim_data,
                                             info_str=('Version 2.0.0, '
                                                       'last updated: '
                                                       'January 2022')))


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
            'form': to_help_dict(TABS.trellis.formclass()),
            'key': TABS.trellis.name
        },
        'residuals': {
            'title': TABS.residuals.title,
            'path': " or ".join(TABS.residuals.viewclass.urls),
            'form': to_help_dict(TABS.residuals.formclass()),
            'key': TABS.residuals.name
        },
        'testing': {
            'title': TABS.testing.title,
            'path': " or ".join(TABS.testing.viewclass.urls),
            'form': to_help_dict(TABS.testing.formclass()),
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
                       gmt=_get_gmdb_column_desc(),
                       )
                  )


def _get_gmdb_column_desc(as_html=True):
    ret = {}
    # # FIXME CHECK
    # for ff_field in FlatfileField.objects.all():
    #     name = ff_field.name
    #     props = ff_field.properties
    #     dtype = props['dtype']
    #     if isinstance(dtype, (list, tuple)):
    #         type2str = 'categorical. Possible values:\n' + \
    #                    "\n".join(str(_) for _ in dtype)
    #     else:
    #         type2str = str(dtype)
    #     default = str(props.get('default', ''))
    #     if as_html:
    #         type2str = "<span style='white-space: nowrap'>%s</span>" % \
    #             type2str.replace('\n', '<br>')
    #     ret[name] = (type2str, default)
    return ret


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
    formclass = TABS[tab_name].formclass
    inputdict = yaml.safe_load(StringIO(request.body.decode('utf-8')))
    dataform = formclass(data=inputdict)  # pylint: disable=not-callable
    if not dataform.is_valid():
        verr = dataform.validation_errors()
        return error_response(verr['message'], verr['code'],
                              errors=verr['errors'])
    buffer = StringIO()
    ext_nodot = os.path.splitext(filename)[1][1:].lower()
    dump_request_data(dataform, buffer, syntax=ext_nodot)
    buffer.seek(0)
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


def download_astext(request, tab_name, filename, text_sep=',', text_dec='.'):
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
    response = formclass.processed_data_as_csv(inputdict, text_sep, text_dec)
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
