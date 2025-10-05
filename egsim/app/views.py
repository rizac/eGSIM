"""
Django views for the eGSIM app (web app with frontend)
"""
from io import BytesIO, StringIO
from itertools import chain
from os.path import splitext
from typing import Optional, Union, Type
import re

from django.forms import IntegerField, BooleanField, CharField, FloatField
from shapely.geometry import shape

from django.http import FileResponse, HttpResponseBase, HttpRequest, JsonResponse
from django.shortcuts import render
from django.conf import settings

from ..api import models
from ..api.forms.flatfile import (FlatfileMetadataInfoForm,
                                  FlatfileValidationForm)
from ..api.forms import APIForm, EgsimBaseForm, GsimForm, GsimInfoForm
from ..api.forms.residuals import ResidualsForm
from ..api.forms.scenarios import PredictionsForm, ArrayField
from ..api.urls import MODEL_INFO_URL_PATH, RESIDUALS_URL_PATH, PREDICTIONS_URL_PATH
from ..api.views import MimeType, EgsimView, GsimInfoView, PredictionsView, ResidualsView
from .forms import PredictionsVisualizeForm, FlatfileVisualizeForm
from ..smtk.registry import Clabel

img_ext = ('png', 'pdf', 'svg')
data_ext = ('hdf', 'csv')
oq_version = '3.15.0'
oq_gmm_refs_page = "https://docs.openquake.org/oq-engine/3.15/reference/"


class URLS:  # noqa
    """Define global URLs, to be used in both urls.py and injected in the web page"""

    # webpage URLs NOTE: DO NOT SUPPLY NESTED PATHS (i.e., NO "/" in PATHS):
    WEBPAGE_HOME = 'home'
    WEBPAGE_DATA_PROTECTION = 'https://www.gfz.de/en/data-protection/'
    WEBPAGE_FLATFILE_COMPILATION_INFO = 'flatfile'
    WEBPAGE_FLATFILE_INSPECTION_PLOT = 'flatfile-visualize'
    WEBPAGE_IMPRINT = "imprint"
    WEBPAGE_PREDICTIONS = 'predictions'
    WEBPAGE_RESIDUALS = 'residuals'
    WEBPAGE_CITATIONS_AND_LICENSE = "citations_and_license"
    WEBPAGE_API_DOC = "api_doc"

    # download URls. NOTE: ALL URLS ARE IN THE FORM: <path>/<downloaded_file_basename>
    DOWNLOAD_PREDICTIONS_DATA = 'download/egsim-predictions'
    DOWNLOAD_PREDICTIONS_PLOT = 'download/egsim-predictions-plot'
    DOWNLOAD_RESIDUALS_DATA = 'download/egsim-residuals'
    DOWNLOAD_RESIDUALS_PLOT = 'download/egsim-residuals-plot'
    DOWNLOAD_FLATFILE_PLOT = 'download/egsim-flatfile-plot'

    # URLs (usually submit buttons) to visualize data on the page:
    SUBMIT_PREDICTIONS_VISUALIZATION = 'submit/egsim-predictions'
    SUBMIT_RESIDUALS_VISUALIZATION = 'submit/egsim-residuals'
    SUBMIT_FLATFILE_VISUALIZATION = 'submit/flatfile'
    SUBMIT_FLATFILE_COMPILATION_INFO = 'submit/flatfile_compilation_info'

    # Misc (usually AJAX requests. NOTE: MOST LIKELY THESE URLs ARE SHARED BETWEEN FORMS)
    GSIMS_FROM_REGION = 'get_models_from_region'
    FLATFILE_VALIDATION = 'get_flatfile_validation'
    GSIMS_INFO = 'get_models_info'
    PREDICTIONS_DOWNLOADED_DATA_TUTORIAL = 'predictions-in-your-code-tutorial.html'
    RESIDUALS_DOWNLOADED_DATA_TUTORIAL = 'residuals-in-your-code-tutorial.html'


# this check is needed to avoid nested paths in url pages
if any(
        "/" in getattr(URLS, _) and not getattr(URLS, _).startswith('https://')
        for _ in dir(URLS) if 'WEBPAGE' in _
):
    raise SystemError("Remove '/' in URL WEBPAGES: '/' create nested paths which might "
                      "mess up requests performed on the page (error 404)")


############################################
# Django Views (helpers + utilities below) #
############################################


def main(request, page=''):
    """view for the main page"""
    regionalizations = list(models.Regionalization.queryset())
    flatfiles = list(models.Flatfile.queryset())
    init_data = get_init_data_json(regionalizations, flatfiles, settings.DEBUG)
    init_data['currentPage'] = page or URLS.WEBPAGE_HOME
    return render(
        request,
        template_name='egsim.html',
        context={
            'debug': settings.DEBUG,
            'init_data': init_data,
            'oq_version': oq_version,
            'oq_gmm_refs_page': oq_gmm_refs_page,
            'references': get_references(regionalizations, flatfiles),
            'api_doc': get_api_doc_data(
                regionalizations, flatfiles, f'{request.scheme}://{request.get_host()}'
            )
        }
    )


class GsimFromRegion(EgsimView):
    """View handling clicks on the GUI map and returning region-selected model(s)"""

    def response(self,
                 request: HttpRequest,
                 data: dict,
                 files: Optional[dict] = None) -> HttpResponseBase:
        form = GsimForm(data)
        if form.is_valid():
            gm_models = form.cleaned_data['regionalization']
        else:
            gm_models = {}
        return JsonResponse({'models': gm_models}, status=200)


class PlotsImgDownloader(EgsimView):
    """View returning the browser displayed plots in image format"""

    def response(self,
                 request: HttpRequest,
                 data: dict,
                 files: Optional[dict] = None) -> HttpResponseBase:
        """Process the response from a given request and the data / files
        extracted from it"""
        filename = request.path[request.path.rfind('/') + 1:]
        img_format = splitext(filename)[1][1:].lower()
        try:
            content_type = getattr(MimeType, img_format)
        except AttributeError:
            return self.error_response(f'Invalid format "{img_format}"')

        from plotly import graph_objects as go, io as pio
        fig = go.Figure(data=data['data'], layout=data['layout'])
        # fix for https://github.com/plotly/plotly.py/issues/3469:
        pio.full_figure_for_development(fig, warn=False)
        img_bytes = fig.to_image(
            format=img_format, width=data['width'], height=data['height'], scale=5
        )
        return FileResponse(
            BytesIO(img_bytes),
            content_type=content_type,
            filename=filename,
            as_attachment=True
        )


class PredictionsHtmlTutorial(EgsimView):
    """View returning the HTML page(s) explaining predictions table structure"""

    def response(self,
                 request: HttpRequest,
                 data: dict,
                 files: Optional[dict] = None) -> HttpResponseBase:
        """Process the response from a given request and the data / files
        extracted from it"""
        from egsim.api.client.snippets.get_egsim_predictions import \
            get_egsim_predictions
        api_form = PredictionsForm({
            'gsim': ['CauzziEtAl2014', 'BindiEtAl2014Rjb'],
            'imt': ['PGA', 'SA(0.1)'],
            'magnitude': [4, 5, 6],
            'distance': [10, 100]
        })
        return render(
            request,
            template_name='downloaded-data-tutorial.html',
            context=get_html_tutorial_context(
                'predictions', api_form, get_egsim_predictions
            )
        )


class ResidualsHtmlTutorial(EgsimView):
    """View returning the HTML page(s) explaining residuals table structure"""

    def response(self,
                 request: HttpRequest,
                 data: dict,
                 files: Optional[dict] = None) -> HttpResponseBase:
        """Process the response from a given request and the data / files
        extracted from it"""
        from egsim.api.client.snippets.get_egsim_residuals import \
            get_egsim_residuals
        api_form = ResidualsForm({
            'gsim': ['CauzziEtAl2014', 'BindiEtAl2014Rjb'],
            'imt': ['PGA'],
            'data-query': '(mag > 7) & (vs30 > 1100)',
            'flatfile': 'esm2018'
        })
        return render(
            request,
            template_name='downloaded-data-tutorial.html',
            context=get_html_tutorial_context(
                'residuals', api_form, get_egsim_residuals
            )
        )


######################
# Utilities / Helpers
######################


def get_init_data_json(
        db_regionalizations: list[models.Regionalization],
        db_flatfiles: list[models.Flatfile],
        debug=False
) -> dict:
    """Return the JSON data to be passed to the browser at startup to initialize
    the page content

    :param debug: True or False, the value of the settings DEBUG flag
    """
    gsims = []
    imt_groups: dict[tuple, int] = {}  # noqa
    warning_groups: dict[str, int] = {}  # noqa
    for gsim in models.Gsim.queryset():
        # imt_names should be hashable and unique, so sort and make a tuple:
        imt_names = tuple(sorted(gsim.imts.split(" ")))
        imt_group_index = imt_groups.setdefault(imt_names, len(imt_groups))
        sa_limits = [gsim.min_sa_period, gsim.max_sa_period]
        if sa_limits[0] is None or sa_limits[1] is None:
            sa_limits = []
        model_warnings = []
        if gsim.unverified:
            model_warnings.append(models.Gsim.unverified.field.help_text)
        if gsim.experimental:
            model_warnings.append(models.Gsim.experimental.field.help_text)
        if gsim.adapted:
            model_warnings.append(models.Gsim.adapted.field.help_text)
        if model_warnings:
            warning_text = "; ".join(model_warnings)
            warning_group_index = warning_groups.setdefault(warning_text,
                                                            len(warning_groups))
            gsims.append([gsim.name, imt_group_index, sa_limits, warning_group_index])
        else:
            gsims.append([gsim.name, imt_group_index, sa_limits])

    # get regionalization data (for selecting models on a map):
    regionalizations = []
    for regx in db_regionalizations:
        regionalizations.append({
            'name': regx.name,
            'bbox': get_bbox(regx),  # tuple (min_lng, min_lat, max_lng, max_lat)
            'url': regx.url or ""
        })

    # get predefined flatfiles info:
    flatfiles = []
    for ffile in db_flatfiles:
        ff_form = FlatfileValidationForm({'flatfile': ffile.name})
        if ff_form.is_valid():
            flatfiles.append({
                'value': ffile.name,
                'name': ffile.name,
                'innerHTML': get_display_name(ffile, extended=True),
                'url': ffile.url,  # noqa
                'columns': ff_form.output()['columns']
            })

    predictions_form = PredictionsForm({
        'gsim': [],
        'imt': [],
        'magnitude': [],  # required
        'distance': [],  # required
        'format': 'hdf'
    })
    residuals_form = ResidualsForm({
        'gsim': [],
        'imt': [],
        'format': 'hdf'
    })
    if debug:
        predictions_form = PredictionsForm({
            'gsim': ['CauzziEtAl2014', 'BindiEtAl2014Rjb'],
            'imt': ['SA(0.05)', 'SA(0.075)'],  # default_imts,
            'magnitude': [4, 5, 6, 7],
            'distance': [1, 10, 100, 1000],
            'format': 'hdf'
        })
        residuals_form = ResidualsForm({
            'gsim': ['CauzziEtAl2014', 'BindiEtAl2014Rjb'],
            'imt': ['PGA', 'SA(0.1)'],
            'flatfile': 'esm2018',
            'flatfile-query': 'mag > 7',
            'format': 'hdf'
        })

    return {
        'pages': {  # tab key => url path (after the first slash)
            'predictions': URLS.WEBPAGE_PREDICTIONS,
            'residuals': URLS.WEBPAGE_RESIDUALS,
            'flatfile_meta_info': URLS.WEBPAGE_FLATFILE_COMPILATION_INFO,
            'flatfile_visualize': URLS.WEBPAGE_FLATFILE_INSPECTION_PLOT,
            'citations_and_license': URLS.WEBPAGE_CITATIONS_AND_LICENSE,
            'imprint': URLS.WEBPAGE_IMPRINT,
            'home': URLS.WEBPAGE_HOME,
            'data_protection': URLS.WEBPAGE_DATA_PROTECTION,
            'api_doc': URLS.WEBPAGE_API_DOC
        },
        'urls': {
            'predictions': URLS.DOWNLOAD_PREDICTIONS_DATA,
            'predictions_visualize': URLS.SUBMIT_PREDICTIONS_VISUALIZATION,
            'predictions_plot_img': [
                f'{URLS.DOWNLOAD_PREDICTIONS_PLOT}.{ext}' for ext in img_ext
            ],
            'predictions_response_tutorial': URLS.PREDICTIONS_DOWNLOADED_DATA_TUTORIAL,
            'residuals': URLS.DOWNLOAD_RESIDUALS_DATA,
            'residuals_visualize': URLS.SUBMIT_RESIDUALS_VISUALIZATION,
            'residuals_plot_img': [
                f'{URLS.DOWNLOAD_RESIDUALS_PLOT}.{ext}' for ext in img_ext
            ],
            'residuals_response_tutorial': URLS.RESIDUALS_DOWNLOADED_DATA_TUTORIAL,
            'flatfile_meta_info': URLS.SUBMIT_FLATFILE_COMPILATION_INFO,
            'flatfile_visualize': URLS.SUBMIT_FLATFILE_VISUALIZATION,
            'flatfile_plot_img': [
                f'{URLS.DOWNLOAD_FLATFILE_PLOT}.{ext}' for ext in img_ext
            ],
            'get_gsim_info': URLS.GSIMS_INFO,
            'get_gsim_from_region': URLS.GSIMS_FROM_REGION,
            'flatfile_validate': URLS.FLATFILE_VALIDATION,
        },
        'forms': {
            'predictions': form2dict(predictions_form),
            # in frontend, the form data below will be merged into forms.residuals above
            # (keys below will take priority):
            'predictions_plot': {'plot_type': 'm', 'format': 'json'},
            'residuals': form2dict(residuals_form),
            # in frontend, the form data below will be merged with forms.residuals above
            # (keys below will take priority):
            'residuals_plot': {'x': None, 'format': 'json'},
            'flatfile_meta_info': form2dict(
                FlatfileMetadataInfoForm({'gsim': []})
            ),
            'flatfile_visualize': form2dict(FlatfileVisualizeForm({})),
            'misc': {
                'predictions': {
                    'msr': predictions_form.fields['msr'].choices,
                    'region': predictions_form.fields['region'].choices,
                    'help': form2help(PredictionsForm),
                    'tutorial_page_visible': False
                },
                'predictions_plot': {
                    'plot_types': PredictionsVisualizeForm.
                    declared_fields['plot_type'].choices
                },
                'flatfile_visualize': {
                    'selected_flatfile_fields': [],
                    'help': form2help(FlatfileVisualizeForm),
                },
                'residuals': {
                    'selected_flatfile_fields': [],
                    'help': form2help(ResidualsForm),
                    'tutorial_page_visible': False
                },
                'flatfile_meta_info': {},
                'download_formats': data_ext
            }
        },
        'responses': {
            'predictions_plots': [],
            'residuals_plots': [],
            'flatfile_meta_info': None,
            'flatfile_visualize': [],
        },
        'gsims': gsims,
        # return the list of imts (imt_groups keys) in the right order:
        'imt_groups': sorted(imt_groups, key=imt_groups.get),
        # return the list of warnings (warning_groups keys) in the right order:
        'warning_groups': sorted(warning_groups, key=warning_groups.get),
        'flatfiles': flatfiles,
        'regionalizations': regionalizations
    }


def get_references(
        db_regionalizations: list[models.Regionalization],
        db_flatfiles: list[models.Flatfile]
):
    """Return the references of the data used by the program"""
    refs = {}
    for item in chain(db_regionalizations, db_flatfiles):
        url = get_url(item)
        if not url:
            continue
        refs[get_display_name(item)] = url

    return refs


def get_api_doc_data(
        db_regionalizations: list[models.Regionalization],
        db_flatfiles: list[models.Flatfile],
        url_host
):
    model_info_params = form2help(GsimInfoForm, compact=False)
    model_to_model_params = form2help(PredictionsForm, compact=False)
    model_to_data_params = form2help(ResidualsForm, compact=False)

    # API ModelInfo: customize help text of parameter "model":
    model_info_params['gsim']['help'] = (
        'The input model(s). Input a string of text to be used to return the matching '
        'models (the search is case-insensitive). The OpenQuake model names generally '
        'follow the format [AuthorYearAdditionalInformation]'
    )

    # All APIs: replace https://... with anchor tags:
    # DO THIS NOW before manipulating other refs and links (see below)
    for form_params in (model_info_params, model_to_model_params, model_to_data_params):
        for key in form_params:
            form_params[key]['help'] = re.sub(
                r"(https?\:\/\/.*?)\)",
                r"<a target='_blank' href='\1'>\1</a>)",
                form_params[key]['help']
            )

    # API ModelToData: customize help text of parameter "model":

    refs = get_hyperlink_text(db_flatfiles)
    if refs:
        refs = f'. References: {refs}'

    flatfile_help = (
        'When user-defined, it must be uploaded with the request. When pre-defined, '
        f'the value must be chosen from: {", ".join(_.name for _ in db_flatfiles)}. '
        f'For a correct usage, please consult the Python notebook examples or the GUI'
        f'{refs}'
    )
    model_to_data_params['flatfile']['help'] += f". {flatfile_help}"

    # All APIs: customize help text of parameter "regionalization":

    refs = get_hyperlink_text(db_regionalizations)
    if refs:
        refs = f'. References: {refs}'

    regionalizations_help = (
        'Values can be one or more string of texts to be '
        f'chosen from {", ".join(_.name for _ in db_regionalizations)}{refs}'
    )
    model_info_params['regionalization']['help'] += regionalizations_help
    model_to_model_params['regionalization']['help'] += regionalizations_help
    model_to_data_params['regionalization']['help'] += regionalizations_help

    # add format param:
    model_info_formats = list(GsimInfoView.supported_formats())
    if len(model_info_formats) > 1:
        model_info_params['format'] = {
            'names': ['format'],
            'help': (f'The response format. A value to be chosen from: '
                     f'{", ".join(model_info_formats)}')
        }
    model_to_model_formats = list(PredictionsView.supported_formats())
    if len(model_to_model_formats) > 1:
        model_to_model_params['format'] = {
            'names': ['format'],
            'help': (f'The response format. A value to be chosen from: '
                     f'{", ".join(model_to_model_formats)}')
        }
    model_to_data_formats = list(ResidualsView.supported_formats())
    if len(model_to_data_formats) > 1:
        model_to_data_params['format'] = {
            'names': ['format'],
            'help': (f'The response format. A value to be chosen from: '
                     f'{", ".join(model_to_data_formats)}')
        }

    return {
        'Model info': {
            'response_format': ", ".join(_.upper() for _ in model_info_formats),
            'url_path': f'{url_host}/{MODEL_INFO_URL_PATH}',
            'type': 'GET or POST',
            'params': model_info_params
        },
        'Model-to-Model': {
            'response_format': ", ".join(_.upper() for _ in model_to_model_formats),
            'url_path': f'{url_host}/{PREDICTIONS_URL_PATH}',
            'type': 'GET or POST',
            'params': model_to_model_params
        },
        'Model-to-Data': {
            'response_format': ", ".join(_.upper() for _ in model_to_data_formats),
            'url_path': f'{url_host}/{RESIDUALS_URL_PATH}',
            'type': 'POST (GET with pre-defined flatfiles only)',
            'params': model_to_data_params
        },
    }


def get_hyperlink_text(
        db_objs: list[Union[models.Flatfile, models.Regionalization]],
        sep=', '
):
    """
    Return all references URL from the given objects, in a string containing
    a series of anchor tags `<a ref='...'>` concatenated with `sep` (", " by default)
    """
    refs = {}
    for db_obj in db_objs:
        url = get_url(db_obj)
        if not url:
            continue
        name = get_display_name(db_obj)
        refs[name] = f"<a target='_blank' href='{url}'>{name}</a>"

    if not refs:
        return ""
    return sep.join(refs[k] for k in sorted(refs))


def get_display_name(
        obj: Union[models.Flatfile, models.Regionalization],
        extended=False
) -> str:
    """return the name from the given Database obj, assuring it is not empty (either
    display_name or name, or, if extended is True (default: False) both of them"""
    display_name = obj.display_name
    name = obj.name
    if not display_name:
        return name
    return f'{name} ({display_name})' if extended else display_name


def get_url(obj: models.Reference) -> str:
    """return the URL or the DOI url from the given Reference obj"""
    if obj.url:
        return obj.url
    return f'https://doi.org/{obj.doi}' if obj.doi else ''


def get_bbox(reg: models.Regionalization) -> list[float]:
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


def form2help(form: Union[EgsimBaseForm, Type[EgsimBaseForm]], compact=True) -> dict:
    """
    Return the given form in a dict with all field names mapped to their help text

    If compact is False (default: True) each dict value is not a string but a dict
    with two keys: names (mapped to all parameter names, 1st is the default) and
    help (a more verbose, human-readable form of the field help text, including also
    other information such as data types and possible choices)
    """
    help_texts = {n: str(f.help_text) or '' for n, f in form.declared_fields.items()}
    if compact:
        return help_texts
    ret = {}
    for n, f in form.declared_fields.items():
        choices = [_[1] for _ in getattr(f, 'choices', [])]
        extra_help = ''
        if choices:
            extra_help = 'The value must to be chosen from ' + ", ".join(choices)
        else:
            plural = isinstance(f, ArrayField)
            num_fields = 0
            if plural:
                num_fields = len(f.base_fields)
                f = f.base_fields[0]

            if isinstance(f, FloatField):
                if plural:
                    extra_help = f'The values must be numeric'
                else:
                    extra_help = f'The value must be numeric'
            elif isinstance(f, IntegerField):  # after FloatField
                if plural:
                    extra_help = f'The values must be numeric integers'
                else:
                    extra_help = f'The value must be a numeric integer'
            elif isinstance(f, BooleanField):
                if plural:
                    extra_help = f'The values must be either true or false'
                else:
                    extra_help = f'The value must be true or false'
            elif isinstance(f, CharField):
                if plural:
                    extra_help = f'The values must be strings of text'
                else:
                    extra_help = f'The value must be a string of text'

            if extra_help and num_fields > 1:
                extra_help.replace('The values ', f'The {num_fields} values')
            elif not extra_help and plural:
                if num_fields == 1:
                    extra_help = f'The values can be provided multiple times'
                else:
                    extra_help = f'The value must be provided {num_fields} times'

        help_text = help_texts[n]
        if help_text and extra_help:
            help_text += f'. {extra_help}'
        elif extra_help:
            help_text = extra_help
        ret[n] = {
            'names': form.param_names_of(n),
            'help': help_text
        }
    return ret


def form2dict(form: EgsimBaseForm, compact=False) -> dict:
    """Return the `data` argument passed in the form
    constructor in a JSON serializable dict

    @param form: the EgsimBaseForm (Django Form subclass)
    @param compact: skip optional parameters, i.e. those whose value equals
        the default when missing
    """
    ret = {}
    for field_name, value in form.data.items():
        if compact:
            field = form.declared_fields.get(field_name, None)
            if field is None:
                continue
            is_field_optional = not field.required or field.initial is not None
            if field is not None and is_field_optional:
                if field.initial == value:
                    continue
        ret[form.param_name_of(field_name)] = value
    return ret


def get_html_tutorial_context(
        key: str,
        api_form: APIForm,
        api_client_function
) -> dict:
    """Return the context (dict) for the Django rendering of the HTML tutorial page"""
    # create dataframe htm:
    s = StringIO()
    if not api_form.is_valid():
        raise ValueError('The Form for the current tutorial is invalid, change config. '
                         'Cannot execute Python code')

    dataframe = api_form.output()
    s.write(to_html(dataframe))

    if key == 'residuals':
        s.write('Or, if ranking=True:')
        api_form.cleaned_data['ranking'] = True
        s.write(to_html(api_form.output()))

    dataframe_html = s.getvalue()

    # create explanation (from code snippet docstring):
    dataframe_info = api_client_function.__doc__
    dataframe_info = dataframe_info[dataframe_info.index('Returns:'):]
    dataframe_info = re.split(r"\n\s*\n", dataframe_info)  # split strings
    dataframe_info = dataframe_info[2:]  # remove 1st 2 lines

    # create selection executions:
    py_select_exprs = {
        'Select by IMT (PGA)':
            'dframe[[c for c in dframe.columns if c.startswith("PGA ")]]',
        'Select by model (BindiEtAl2014Rjb)':
            'dframe[[c for c in dframe.columns if c.endswith(" BindiEtAl2014Rjb")]]',
        'Select all input data':
            f'dframe[[c for c in dframe.columns if c.startswith("{Clabel.input} ")]]',
    }
    if key == 'residuals':
        py_select_exprs['Select by metric type (Total residuals)'] = \
            f'dframe[[c for c in dframe.columns if " {Clabel.total_res} " in c]]'
    else:
        py_select_exprs['Select by metric type (Medians)'] = \
            f'dframe[[c for c in dframe.columns if " {Clabel.median} " in c]]'

    py_select_snippets = []
    for title, expr in py_select_exprs.items():
        py_select_snippets.append([
            title, expr, to_html(eval(expr, {'dframe': dataframe}), max_rows=3)]
        )

    return {
        'key': key,
        'dataframe_html': dataframe_html,
        'dataframe_info': dataframe_info,
        'py_select_snippets': py_select_snippets
    }


def to_html(dataframe, **kwargs):
    kwargs.setdefault('classes', 'table table-bordered table-light my-0')
    kwargs.setdefault('border', 0)
    kwargs.setdefault('max_rows', 3)
    kwargs.setdefault('max_cols', None)
    kwargs.setdefault('index', True)
    buffer = StringIO()
    dataframe.to_html(buffer, **kwargs)
    # No cell text wrapping. Note that pandas might add style, so add Bootstrap5 class:
    return re.sub(r"<t([dh])([ >])", r'<t\1 class="text-nowrap"\2', buffer.getvalue())
