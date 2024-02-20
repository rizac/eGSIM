"""
Created on 17 Jan 2018

@author: riccardo
"""
import os

from django.http import FileResponse
from io import StringIO, BytesIO
import json
import yaml
from shapely.geometry import shape

from django.http.response import HttpResponse, JsonResponse
from django.shortcuts import render
from django.conf import settings
# from django.views.decorators.clickjacking import xframe_options_sameorigin


from ..api import models
from ..api.forms.flatfile import FlatfileForm
from ..api.forms.flatfile.compilation import (FlatfileRequiredColumnsForm,
                                              FlatfileInspectionForm, FlatfilePlotForm)
from ..api.forms import GsimFromRegionForm
from ..api.views import (error_response, RESTAPIView, TrellisView, ResidualsView,
                         MimeType)
from ..smtk import intensity_measures_defined_for


class URLS:  # noqa
    """Define global URLs"""
    # NOTE NO URL HERE (unless external, i.e., http://) MUST END WITH  "/"

    # FIXME REMOVE BELOW
    # JSON data requested by the main page at startup:
    #  MAIN_PAGE_INIT_DATA = "init_data"

    # Url for getting the gsim list from a given geographic location:
    # FIXME: MOVE OUT OF REGIONALIZATION dict
    GET_GSIMS_FROM_REGION = 'data/get_models_from_region'
    # inspecting a flatfile:
    FLATFILE_INSPECTION = 'data/flatfile_inspection'
    # FLATFILE_REQUIRED_COLUMNS = 'data/flatfile_required_columns'
    # FLATFILE_PLOT = 'data/flatfile_plot'
    # DOWNLOAD_REQUEST = 'data/downloadrequest'
    # DOWNLOAD_RESPONSE = 'data/downloadresponse'
    # info pages:
    # HOME_NO_MENU = 'home_no_menu'
    # API = 'api'
    HOME_PAGE = 'home'
    DATA_PROTECTION_PAGE = 'https://www.gfz-potsdam.de/en/data-protection/'
    FLATFILE_INFO_PAGE = 'flatfile-info'
    FLATFILE_VISUALIZER_PAGE = 'flatfile-visualizer'
    IMPRINT_PAGE = "imprint"
    PREDICTIONS_PAGE = 'predictions'
    RESIDUALS_PAGE = 'residuals'
    REF_AND_LICENSE_PAGE = "ref_and_license"


def main(request, page=''):
    """view for the main page"""
    # FIXME: REMOVE egsim.py entirely, as well as apidoc.py!
    template = 'egsim.html'
    # fixme: handle regionalization (set to None cause otherwise is not JSON serializable)!
    inits = {'gsim': [], 'imt': [], 'regionalization': None}
    trellis_form = TrellisView.formclass({'magnitude': [1, 2], 'distance': [3], **inits})
    residuals_form = ResidualsView.formclass(inits)
    forms_data_json = {
        'forms': {
            'trellis': trellis_form.asdict(),
            'residuals': residuals_form.asdict(),
            'flatfile_compilation': dict(inits),
            'flatfile_inspection': FlatfilePlotForm({}).asdict(),
            'misc': {
                'msr': trellis_form.fields['msr'].choices,
                'region': trellis_form.fields['region'].choices,
                'flatfile_inspection_columns': []
            }
        }
    }
    init_data = _get_init_data_json() | forms_data_json | {'currentPage': page or URLS.HOME_PAGE}
    return render(request, template, context={'debug': settings.DEBUG,
                                              'init_data': init_data,
                                              'references': _get_references()})


def _get_init_data_json(browser: dict = None,
                        selected_menu: str = None,
                        debug=True) -> dict:
    """Return the JSON data to be passed to the browser at startup to initialize
    the page content

    :param browser: a dict with 'name':str and 'version': float keys
    """
    # check browser:
    allowed_browsers = {'chrome': 49, 'firefox': 45, 'safari': 10}
    allowed_browsers_msg = ', '.join(f'{b.title()}≥{v}'
                                     for b, v in allowed_browsers.items())
    invalid_browser_message = (f'eGSIM could not determine if your browser '
                               f'matches {allowed_browsers_msg}. '
                               f'This portal might not work as expected')
    browser_name = (browser or {}).get('name', None)
    browser_ver = (browser or {}).get('version', None)
    if browser_ver is not None:
        a_browser_ver = allowed_browsers.get(browser_name.lower(), None)
        if a_browser_ver is not None and browser_ver >= a_browser_ver:
            invalid_browser_message = ''

    gsims = []
    imt_groups = []
    warning_groups = []
    db_warnings = {
        models.Gsim.unverified.field.name: models.Gsim.unverified.field.help_text,
        models.Gsim.experimental.field.name: models.Gsim.experimental.field.help_text,
        models.Gsim.adapted.field.name: models.Gsim.adapted.field.help_text
    }
    for gsim in models.Gsim.queryset('name', *db_warnings):
        imt_names = sorted(intensity_measures_defined_for(gsim.name))
        model_warnings = []
        for field_name, field_help in db_warnings.items():
            if getattr(gsim, field_name) is True:
                model_warnings.append(field_help)  # noqa
        try:
            imt_group_index = imt_groups.index(imt_names)
        except ValueError:
            imt_group_index = len(imt_groups)
            imt_groups.append(imt_names)
        if model_warnings:
            warning_text = "; ".join(model_warnings)
            try:
                warning_group_index = warning_groups.index(warning_text)
            except ValueError:
                warning_group_index = len(warning_groups)
                warning_groups.append(warning_text)
            gsims.append([gsim.name, imt_group_index, warning_group_index])
        else:
            gsims.append([gsim.name, imt_group_index])

    # get regionalization data (for selecting models on a map):
    regs = list(models.Regionalization.queryset('name', 'url', 'media_root_path'))
    regionalizations = {
        'url': URLS.GET_GSIMS_FROM_REGION,
        'names': [r.name for r in regs],
        # bbox are tuples of the form (min_lng, min_lat, max_lng, max_lat):
        'bbox': {r.name: _get_bbox(r) for r in regs},
        'ref': {r.name: r.url or "" for r in regs}
    }

    # get predefined flatfiles info:
    flatfiles = []
    for ffile in models.Flatfile.queryset('name', 'display_name', 'url', 'media_root_path'):
        flatfiles .append({
            'value': ffile.name,
            'key': ffile.name,
            'innerHTML': f'{ffile.name} ({ffile.display_name})',  # noqa
            'url': ffile.url,  # noqa
            'columns': FlatfileForm.get_flatfile_dtypes(ffile.read_from_filepath(nrows=0))
        })

    # Get component props (core data needed for Vue rendering):
    # components_props = get_components_properties(debug)


    return {
        'pages': {  # tab key => url path (after the first slash)
            'predictions': URLS.PREDICTIONS_PAGE,
            'residuals': URLS.RESIDUALS_PAGE,
            'flatfile_info': URLS.FLATFILE_INFO_PAGE,
            'flatfile_visualizer': URLS.FLATFILE_VISUALIZER_PAGE,
            'ref_and_license': URLS.REF_AND_LICENSE_PAGE,
            'imprint': URLS.IMPRINT_PAGE,
            'home': URLS.HOME_PAGE,
            'data_protection': URLS.DATA_PROTECTION_PAGE
        },
        'urls': {
            'trellis': TrellisView.urls[0],
            'residuals': ResidualsView.urls[0],
            'flatfile_upload': URLS.FLATFILE_INSPECTION,
            # 'flatfile_inspection': 'data/flatfile_plot',
            # 'flatfile_compilation': 'data/flatfile_required_columns'
        },
        'gsims': gsims,
        'imt_groups': imt_groups,
        'warning_groups': warning_groups,
        'flatfiles': flatfiles,
        'regionalizations': regionalizations
    }


def _get_bbox(reg: models.Regionalization) -> list[float]:
    """Return the bounds of all the regions coordinates in the given regionalization

    @param return: the 4-element list (minx, miny, maxx, maxy) i.e.
        (minLon, minLat, maxLon, maxLat)
    """
    feat_collection = reg.read_from_filepath()
    bounds = [180, 90, -180, -90]  # (minx, miny, maxx, maxy)
    for g in feat_collection['features']:
        bounds_ = shape(g['geometry']).bounds  # (minx, miny, maxx, maxy)
        bounds[0] = min(bounds[0], bounds_[0])
        bounds[1] = min(bounds[1], bounds_[1])
        bounds[2] = max(bounds[2], bounds_[2])
        bounds[3] = max(bounds[3], bounds_[3])
    return bounds


def _get_references():
    """Return the references of the data used by the program"""
    refs = {}
    for model_cls in [models.Regionalization, models.Flatfile]:
        for item in model_cls.queryset().values():
            url = item.get('url', '')
            if not url:
                url = item.get('doi', '')
                if url and not url.startswith('http'):
                    url = f'https://doi.org/{url}'
            if not url:
                continue
            name = item.get('display_name', item['name'])
            refs[name] = url
    return refs


def get_gsims_from_region(request) -> JsonResponse:
    return RESTAPIView.as_view(formclass=GsimFromRegionForm)(request)


def flatfile_required_columns(request) -> JsonResponse:
    return RESTAPIView.as_view(formclass=FlatfileRequiredColumnsForm)(request)


def flatfile_inspection(request) -> JsonResponse:
    return RESTAPIView.as_view(formclass=FlatfileInspectionForm)(request)


def flatfile_plot(request) -> JsonResponse:
    return RESTAPIView.as_view(formclass=FlatfilePlotForm)(request)



# FIXME REMOVE / CLEANUP THE CODE BELOW AND ALL ITS USAGES! ===================

def download_request(request, key, filename: str):
    """Return the request (configuration) re-formatted according to the syntax
    inferred from filename (*.json or *.yaml) to be downloaded by the front
    end GUI.

    :param key: a :class:`TAB` name associated to a REST API TAB (i.e.,
        with an associated Form class)
    """
    form_class = TAB[key].formclass  # FIXME remove pycharm lint warning

    def input_dict() -> dict:
        """return the input dict. This function allows to work each time
        on a new copy of the input data"""
        return yaml.safe_load(StringIO(request.body.decode('utf-8')))

    form = form_class(data=input_dict())
    if not form.is_valid():
        return error_response(form.errors_json_data(), RESTAPIView.CLIENT_ERR_CODE)
    ext_nodot = os.path.splitext(filename)[1][1:].lower()
    compact = True
    if ext_nodot == 'json':
        # in the frontend the axios library expects bytes data (blob)
        # or bytes strings in order for the data to be correctly saved. Thus,
        # use text/javascript because 'application/json' does not work (or should
        # we better use text/plain?)
        response = HttpResponse(StringIO(form.as_json(compact=compact)),
                                content_type='text/javascript')
    # elif ext_nodot == 'querystring':
    #     # FIXME: as_querystring is not part of Form anymore... remove? drop?
    #     response = HttpResponse(StringIO(form.as_querystring(compact=compact)),
    #                             content_type='text/plain')
    else:
        response = HttpResponse(StringIO(form.as_yaml(compact=compact)),
                                content_type='application/x-yaml')
    response['Content-Disposition'] = 'attachment; filename=%s' % filename
    return response


def download_response(request, key, filename: str):
    basename, ext = os.path.splitext(filename)
    if ext == '.csv':
        return download_ascsv(request, key, filename)
    elif ext == '.csv_eu':
        return download_ascsv(request, key, basename + '.csv', ';', ',')
    try:
        return download_asimage(request, filename, ext[1:])
    except AttributeError:
        pass  # filename extension not recognized as image
    return error_response(f'Unsupported format "{ext[1:]}"',
                          RESTAPIView.CLIENT_ERR_CODE)


def download_ascsv(request, key, filename: str, sep=',', dec='.'):
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


def download_asimage(request, filename: str, img_format: str) -> FileResponse:
    """Return the image from the given request built in the frontend GUI
    according to the chosen plots
    """
    content_type = getattr(MimeType, img_format)
    if not filename.lower().endswith(f".{img_format}"):
        filename += f".{img_format}"
    jsondata = json.loads(request.body.decode('utf-8'))
    data, layout, width, height = (jsondata['data'],
                                   jsondata['layout'],
                                   jsondata['width'],
                                   jsondata['height'])
    from plotly import graph_objects as go, io as pio
    fig = go.Figure(data=data, layout=layout)
    # fix for https://github.com/plotly/plotly.py/issues/3469:
    pio.full_figure_for_development(fig, warn=False)
    bytestr = fig.to_image(format=img_format, width=width, height=height, scale=5)
    # FIXME: use the following throughout the code harmonizing how we return files:
    return FileResponse(BytesIO(bytestr), content_type=content_type,
                        filename=filename, as_attachment=True)
    # FIXME: remove?
    # response = HttpResponse(bytestr, content_type=content_type)
    # response['Content-Disposition'] = \
    #     'attachment; filename=%s' % filename
    # response['Content-Length'] = len(bytestr)
    # return response


def _test_err(request):
    """Dummy function raising for front end test purposes. Might be removed
    soon"""
    raise ValueError('this is a test error!')
