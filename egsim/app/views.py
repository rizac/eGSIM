"""
Created on 17 Jan 2018

@author: riccardo
"""
from django.http import FileResponse
from django.views.decorators.clickjacking import xframe_options_exempt
from io import BytesIO, StringIO
import json
from shapely.geometry import shape

from django.http.response import JsonResponse
from django.shortcuts import render
from django.conf import settings

from .forms import ResidualsPlotDataForm, PredictionsPlotDataForm
# from django.views.decorators.clickjacking import xframe_options_sameorigin

from ..api import models
from ..api.forms.flatfile.management import (FlatfileMetadataInfoForm,
                                             FlatfileValidationForm,
                                             FlatfilePlotForm)
from ..api.forms import GsimFromRegionForm, APIForm
from ..api.forms.flatfile.residuals import ResidualsForm
from ..api.forms.predictions import PredictionsForm
from ..api.views import RESTAPIView, TrellisView, ResidualsView, MimeType
from ..smtk import intensity_measures_defined_for


class URLS:  # noqa
    """Define global URLs"""

    GET_GSIMS_FROM_REGION = 'gui/get_models_from_region'
    FLATFILE_VALIDATION = 'gui/flatfile_validation'
    FLATFILE_VISUALIZATION = 'gui/flatfile_visualization'
    FLATFILE_META_INFO = 'gui/get_flatfile_meta_info'

    DOWNLOAD_PREDICTIONS = 'gui/download/egsim-predictions'
    DOWNLOAD_RESIDUALS = 'gui/download/egsim-residuals'
    PREDICTIONS_PLOT = 'gui/egsim-predictions-plot'
    RESIDUALS_PLOT = 'gui/egsim-residuals-plot'

    PREDICTIONS_RESPONSE_TUTORIAL_HTML = 'jupyter/predictions-response-tutorial.html'
    RESIDUALS_RESPONSE_TUTORIAL_HTML = 'jupyter/residuals-response-tutorial.html'

    HOME_PAGE = 'home'
    DATA_PROTECTION_PAGE = 'https://www.gfz-potsdam.de/en/data-protection/'
    FLATFILE_META_INFO_PAGE = 'flatfile-metadata-info'
    FLATFILE_INSPECTION_PLOT_PAGE = 'flatfile-inspection-plot'
    IMPRINT_PAGE = "imprint"
    PREDICTIONS_PAGE = 'predictions'
    RESIDUALS_PAGE = 'residuals'
    REF_AND_LICENSE_PAGE = "ref_and_license"


def main(request, page=''):
    """view for the main page"""
    # FIXME: REMOVE egsim.py entirely, as well as apidoc.py! (DONE, but check for safety)
    template = 'egsim.html'
    # fixme: handle regionalization (set to None cause otherwise is not JSON serializable)!
    init_data = _get_init_data_json(settings.DEBUG) | {'currentPage': page or URLS.HOME_PAGE}
    return render(request, template, context={'debug': settings.DEBUG,
                                              'init_data': init_data,
                                              'references': _get_references()})


def _get_init_data_json(debug=False) -> dict:
    """Return the JSON data to be passed to the browser at startup to initialize
    the page content

    :param debug: True or False, the value of the settings DEBUG flag
    """
    # check browser: FIXME REMOVE?
    # allowed_browsers = {'chrome': 49, 'firefox': 45, 'safari': 10}
    # allowed_browsers_msg = ', '.join(f'{b.title()}≥{v}'
    #                                  for b, v in allowed_browsers.items())
    # invalid_browser_message = (f'eGSIM could not determine if your browser '
    #                            f'matches {allowed_browsers_msg}. '
    #                            f'This portal might not work as expected')
    # browser_name = (browser or {}).get('name', None)
    # browser_ver = (browser or {}).get('version', None)
    # if browser_ver is not None:
    #     a_browser_ver = allowed_browsers.get(browser_name.lower(), None)
    #     if a_browser_ver is not None and browser_ver >= a_browser_ver:
    #         invalid_browser_message = ''

    gsims = []
    imt_groups: dict[tuple, int] = {}  # noqa
    warning_groups: dict[str, int] = {}  # noqa
    db_warnings = {
        'unverified': models.Gsim.unverified.field.help_text,
        'experimental': models.Gsim.experimental.field.help_text,
        'adapted': models.Gsim.adapted.field.help_text
    }
    for gsim in models.Gsim.queryset('name', *list(db_warnings)):
        imt_names = tuple(sorted(intensity_measures_defined_for(gsim.name)))
        imt_group_index = imt_groups.setdefault(imt_names, len(imt_groups))

        model_warnings = []
        for field_name, field_help in db_warnings.items():
            if getattr(gsim, field_name) is True:
                model_warnings.append(field_help)  # noqa
        if model_warnings:
            warning_text = "; ".join(model_warnings)
            warning_group_index = warning_groups.setdefault(warning_text,
                                                            len(warning_groups))
            gsims.append([gsim.name, imt_group_index, warning_group_index])
        else:
            gsims.append([gsim.name, imt_group_index])

    # get regionalization data (for selecting models on a map):
    regionalizations = []
    for regx in models.Regionalization.queryset('name', 'url', 'media_root_path'):
        regionalizations.append({
            'name': regx.name,
            'bbox': _get_bbox(regx),  # tuple (min_lng, min_lat, max_lng, max_lat)
            'url': regx.url or ""
        })

    # get predefined flatfiles info:
    flatfiles = []
    for ffile in models.Flatfile.queryset('name', 'display_name', 'url',
                                          'media_root_path'):
        ff_form = FlatfileValidationForm({'flatfile': ffile.name})
        if ff_form.is_valid():
            flatfiles.append({
                'value': ffile.name,
                'name': ffile.name,
                'innerHTML': f'{ffile.name} ({ffile.display_name})',  # noqa
                'url': ffile.url,  # noqa
                'columns': ff_form.output()['columns']
            })

    # Get component props (core data needed for Vue rendering):
    # components_props = get_components_properties(debug)
    default_models = []
    default_imts = []
    default_data = None
    default_data_query = ''
    if debug:
        default_models = ['CauzziEtAl2014', 'BindiEtAl2014Rjb']
        default_imts = ['PGA', 'SA(0.1)']
        default_data = 'esm2018'
        default_data_query = 'mag > 7'

    predictions_form = TrellisView.formclass({
        'gsim': default_models,
        'imt': default_imts,
        'regionalization': None,
        'magnitude': [1, 2],
        'distance': [3],
        'format': 'hdf'
    })
    residuals_form = ResidualsView.formclass({
        'gsim': default_models,
        'imt': default_imts,
        'flatfile': default_data,
        'data-query': default_data_query,
        'regionalization': None,
        'format': 'hdf'
    })
    return {
        'pages': {  # tab key => url path (after the first slash)
            'predictions': URLS.PREDICTIONS_PAGE,
            'residuals': URLS.RESIDUALS_PAGE,
            'flatfile_meta_info': URLS.FLATFILE_META_INFO_PAGE,
            'flatfile_inspection_plot': URLS.FLATFILE_INSPECTION_PLOT_PAGE,
            'ref_and_license': URLS.REF_AND_LICENSE_PAGE,
            'imprint': URLS.IMPRINT_PAGE,
            'home': URLS.HOME_PAGE,
            'data_protection': URLS.DATA_PROTECTION_PAGE
        },
        'urls': {
            'predictions': URLS.DOWNLOAD_PREDICTIONS,
            'residuals': URLS.DOWNLOAD_RESIDUALS,
            'predictions_plot': URLS.PREDICTIONS_PLOT,
            'residuals_plot': URLS.RESIDUALS_PLOT,
            'get_gsim_from_region': URLS.GET_GSIMS_FROM_REGION,
            'flatfile_meta_info': URLS.FLATFILE_META_INFO,
            'flatfile_inspection_plot': URLS.FLATFILE_VISUALIZATION,
            'flatfile_validation': URLS.FLATFILE_VALIDATION,
            'predictions_response_tutorial': URLS.PREDICTIONS_RESPONSE_TUTORIAL_HTML,
            'residuals_response_tutorial': URLS.RESIDUALS_RESPONSE_TUTORIAL_HTML,
        },
        'forms': {
            'predictions': predictions_form.asdict(),
            # in frontend, the form data below will be merged into forms.residuals above
            # (keys below will take priority):
            'predictions_plot': {'plot_type': 'm', 'format': 'json'},
            'residuals': residuals_form.asdict(),
            # in frontend, the form data below will be merged with forms.residuals above
            # (keys below will take priority):
            'residuals_plot': {'x': None, 'likelihood': False, 'format': 'json'},
            'flatfile_meta_info': FlatfileMetadataInfoForm({
                'gsim': default_models,
                'imt': default_imts,
                'regionalization': None
            }).asdict(),
            'flatfile_inspection_plot': FlatfilePlotForm({}).asdict(),
            'misc': {
                'predictions':{
                    'msr': predictions_form.fields['msr'].choices,
                    'region': predictions_form.fields['region'].choices,
                },
                'predictions_plot':{
                    'plot_types': PredictionsPlotDataForm.base_fields['plot_type'].choices
                },
                'flatfile_inspection_plot': {
                    'selected_flatfile_fields': []
                },
                'residuals': {
                    'selected_flatfile_fields': [],
                },
                'flatfile_meta_info': {
                    'show_dialog': False
                },
                'download_formats': ['hdf', 'csv']
            }
        },
        'responses': {
            'predictions_plots': [],
            'residuals_plots': [],
            'flatfile_meta_info': None,
            'flatfile_inspection_plot': [],
        },
        'gsims': gsims,
        # return the list of imts (imt_groups keys) in the right order:
        'imt_groups': sorted(imt_groups, key=imt_groups.get),
        # return the list of warnings (warning_groups keys) in the right order:
        'warning_groups': sorted(warning_groups, key=warning_groups.get),
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


def flatfile_validation(request) -> JsonResponse:
    return RESTAPIView.as_view(formclass=FlatfileValidationForm)(request)


def flatfile_meta_info(request) -> JsonResponse:
    return RESTAPIView.as_view(formclass=FlatfileMetadataInfoForm)(request)


def flatfile_plot(request) -> JsonResponse:
    return RESTAPIView.as_view(formclass=FlatfilePlotForm)(request)


def predictions_plot(request) -> JsonResponse:
    return RESTAPIView.as_view(formclass=PredictionsPlotDataForm)(request)


def residuals_plot(request) -> JsonResponse:
    return RESTAPIView.as_view(formclass=ResidualsPlotDataForm)(request)


@xframe_options_exempt
def get_predictions_response_tutorial(request):
    from egsim.api.data.client.snippets.get_egsim_predictions import \
        get_egsim_predictions
    api_form = PredictionsForm({
        'gsim': ['CauzziEtAl2014', 'BindiEtAl2014Rjb'],
        'imt': ['PGA', 'SA(0.1)'],
        'magnitude': [4, 5, 6],
        'distance': [10, 100]
    })
    return _get_download_tutorial(request, 'predictions', api_form, get_egsim_predictions)


@xframe_options_exempt
def get_residuals_response_tutorial(request):
    from egsim.api.data.client.snippets.get_egsim_residuals import \
        get_egsim_residuals
    api_form = ResidualsForm({
        'gsim': ['CauzziEtAl2014', 'BindiEtAl2014Rjb'],
        'imt': ['PGA', 'PGV'],
        'data-query': 'mag > 7',
        'flatfile': 'esm2018'
    })
    return _get_download_tutorial(request, 'residuals', api_form, get_egsim_residuals)


def _get_download_tutorial(request, key:str, api_form:APIForm, api_client_function):
    import re
    doc = api_client_function.__doc__
    # replace italic with <em>s:
    doc = re.sub(r'\*(.*?)\*', f'<em>\\1</em>', doc, flags=re.DOTALL)

    doc = doc[doc.index('Returns'):].strip()
    doc = doc.split('\n\n')[1:]
    doc[1] = doc[1].replace('indicating:', 'indicating (cf. table representation above):')
    tbl = doc[2].strip().split("\n")
    table_cls = 'table table-bordered table-light my-2'
    doc[2] = (
        f"<table class=\"{table_cls}\">"
        f"<thead>"
        f"<tr><td>{'</td><td>'.join(tbl[0].split('|')[1:-1])}</td></tr>"
        f"</thead>"
        f"<tbody>"
        f"<tr><td>{'</td><td>'.join(tbl[2].split('|')[1:-1])}</td></tr>"
        f"<tr><td>{'</td><td>'.join(tbl[3].split('|')[1:-1])}</td></tr>"
        f"<tr><td>{'</td><td>'.join(tbl[4].split('|')[1:-1])}</td></tr>"
        "</tbody>"
        "</table>"
    )

    s = StringIO()
    if api_form.is_valid():
        api_form.output().to_html(s, index=True, classes=table_cls, border=0, max_rows=6)
    return render(request, 'downloaded-data-tutorial.html',
                  context={
                      'key': key,
                      'dataframe_html': s.getvalue(),
                      'docstring_intro': doc[0][doc[0].index('where each row'):],
                      'docstring_headers_intro': "\n\n".join(doc[1:])
                  })


# FIXME REMOVE / CLEANUP THE CODE BELOW AND ALL ITS USAGES! ===================

# def download_request(request, key, filename: str):
#     """Return the request (configuration) re-formatted according to the syntax
#     inferred from filename (*.json or *.yaml) to be downloaded by the front
#     end GUI.
#
#     :param key: a :class:`TAB` name associated to a REST API TAB (i.e.,
#         with an associated Form class)
#     """
#     form_class = TAB[key].formclass  # FIXME remove pycharm lint warning
#
#     def input_dict() -> dict:
#         """return the input dict. This function allows to work each time
#         on a new copy of the input data"""
#         return yaml.safe_load(StringIO(request.body.decode('utf-8')))
#
#     form = form_class(data=input_dict())
#     if not form.is_valid():
#         return error_response(form.errors_json_data(), RESTAPIView.CLIENT_ERR_CODE)
#     ext_nodot = os.path.splitext(filename)[1][1:].lower()
#     compact = True
#     if ext_nodot == 'json':
#         # in the frontend the axios library expects bytes data (blob)
#         # or bytes strings in order for the data to be correctly saved. Thus,
#         # use text/javascript because 'application/json' does not work (or should
#         # we better use text/plain?)
#         response = HttpResponse(StringIO(form.as_json(compact=compact)),
#                                 content_type='text/javascript')
#     # elif ext_nodot == 'querystring':
#     #     # FIXME: as_querystring is not part of Form anymore... remove? drop?
#     #     response = HttpResponse(StringIO(form.as_querystring(compact=compact)),
#     #                             content_type='text/plain')
#     else:
#         response = HttpResponse(StringIO(form.as_yaml(compact=compact)),
#                                 content_type='application/x-yaml')
#     response['Content-Disposition'] = 'attachment; filename=%s' % filename
#     return response
#
#
# def download_response(request, key, filename: str):
#     basename, ext = os.path.splitext(filename)
#     if ext == '.csv':
#         return download_ascsv(request, key, filename)
#     elif ext == '.csv_eu':
#         return download_ascsv(request, key, basename + '.csv', ';', ',')
#     try:
#         return download_asimage(request, filename, ext[1:])
#     except AttributeError:
#         pass  # filename extension not recognized as image
#     return error_response(f'Unsupported format "{ext[1:]}"',
#                           RESTAPIView.CLIENT_ERR_CODE)
#
#
# def download_ascsv(request, key, filename: str, sep=',', dec='.'):
#     """Return the processed data as text/CSV. This method is used from within
#     the browser when users want to get processed data as text/csv: as the
#     browser stores the processed data dict, we just need to convert it as
#     text/CSV.
#     Consequently, the request's body is the JSON data resulting from a previous
#     call of the GET or POST method of any REST API View.
#
#     :param key: a :class:`TAB` name associated to a REST API TAB (i.e.,
#         with an associated Form class)
#     """
#     formclass = TAB[key].formclass
#     inputdict = yaml.safe_load(StringIO(request.body.decode('utf-8')))
#     response_data = formclass.to_csv_buffer(inputdict, sep, dec)
#     response = TAB[key].viewclass.response_text(response_data)
#     response['Content-Disposition'] = 'attachment; filename=%s' % filename
#     return response


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


# FIXME TEST REQUESTS REMOVE BELOW

def _test_err(request):
    """Dummy function raising for front end test purposes. Might be removed
    soon"""
    raise ValueError('this is a test error!')


def test_request(request):  # FIXME REMOVE?
    import time
    time.sleep(3)
    # return JsonResponse(data={'message': 'ok'}, status=200)
    return JsonResponse(data={'message': """Examples
Fetching an image

In our basic fetch example (run example live) we use a simple fetch() call to grab an image and display it in an <img> element. The fetch() call returns a promise, which resolves to the Response object associated with the resource fetch operation.

You'll notice that since we are requesting an image, we need to run Response.blob to give the response its correct MIME type."""}, status=400)