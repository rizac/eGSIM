'''
Created on 17 Jan 2018

@author: riccardo
'''
import os
import json
from collections import OrderedDict
from datetime import date

from yaml.error import YAMLError

from django.http import JsonResponse
from django.shortcuts import render
# from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import View
from django.forms.fields import MultipleChoiceField
from django.conf import settings
from django.template.loader import get_template

from egsim.middlewares import ExceptionHandlerMiddleware
from egsim.forms.forms import TrellisForm, GsimSelectionForm, ResidualsForm, \
    BaseForm, GmdbPlot, TestingForm
from egsim.core.utils import QUERY_PARAMS_SAFE_CHARS, get_gmdb_names, get_gmdb_path,\
    get_gmdb_column_desc
from egsim.core import smtk as egsim_smtk
from egsim.forms.fields import ArrayField
from egsim.models import aval_gsims, gsim_names, TrSelector, aval_trmodels
from egsim.forms.htmldoc import to_html_table
from django.template.exceptions import TemplateDoesNotExist


_COMMON_PARAMS = {
    'project_name': 'eGSIM',
    'debug': settings.DEBUG,
    }


def main(request, selected_menu=None):
    '''view for the main page'''

    MENU_HOME = 'home'  # pylint: disable=invalid-name
    MENU_GSIMS = 'gsims'  # pylint: disable=invalid-name
    MENU_TRELLIS = 'trellis'  # pylint: disable=invalid-name
    MENU_GMDB = 'gmdbplot'  # pylint: disable=invalid-name
    MENU_RES = 'residuals'  # pylint: disable=invalid-name
    MENU_TEST = 'testing'  # pylint: disable=invalid-name
    MENU_DOC = 'apidoc'  # pylint: disable=invalid-name

    # Tab components (one per tab, one per activated vue component)
    # (key, label and icon) (the last is bootstrap fontawesome name)
    components_tabs = [(MENU_HOME, 'Home', 'fa-home'),
                       (MENU_GSIMS, 'Gsim selection', 'fa-map-marker'),
                       (MENU_TRELLIS, 'Trellis Plots', 'fa-area-chart'),
                       (MENU_GMDB, 'Ground Motion database', 'fa-database'),
                       (MENU_RES, 'Residuals', 'fa-bar-chart'),
                       (MENU_TEST, 'Testing', 'fa-list'),
                       (MENU_DOC, 'API Documentation', 'fa-info-circle')]
    # this can be changed if needed:
    sel_component = MENU_HOME if not selected_menu else selected_menu

    # properties to be passed to vuejs components:
    components_props = {
        MENU_HOME: {'src': 'pages/home'},
        MENU_GSIMS: {'tr_models_url': 'data/tr_models',
                     'url': GsimsView.url,
                     'form': GsimsView.formclass().to_rendering_dict()},
        MENU_TRELLIS: {'url': TrellisView.url,
                       'form': TrellisView.formclass().to_rendering_dict()},
        MENU_GMDB: {'url': GmdbPlotView.url,
                    'form': GmdbPlotView.formclass().to_rendering_dict()},
        MENU_RES: {'url': ResidualsView.url,
                   'form': ResidualsView.formclass().to_rendering_dict()},
        MENU_TEST: {'url': TestingView.url,
                    'form': TestingView.formclass().to_rendering_dict()},
        MENU_DOC: {'src': 'pages/apidoc'}
    }

    # REMOVE LINES BELOW!!!
    gsimnames = ['AkkarEtAlRjb2014', 'BindiEtAl2014Rjb', 'BooreEtAl2014',
                 'CauzziEtAl2014']
    components_props['trellis']['form']['gsim']['val'] = gsimnames
    components_props['trellis']['form']['imt']['val'] = ['PGA']
    components_props['trellis']['form']['magnitude']['val'] = "5:7"
    components_props['trellis']['form']['distance']['val'] = "10 50 100"
    components_props['trellis']['form']['aspect']['val'] = 1
    components_props['trellis']['form']['dip']['val'] = 60
    components_props['trellis']['form']['plot_type']['val'] = 's'

    components_props['residuals']['form']['gsim']['val'] = gsimnames
    components_props['residuals']['form']['imt']['val'] = ['PGA', 'SA']
    components_props['residuals']['form']['sa_periods']['val'] = "0.2 1.0 2.0"
    components_props['residuals']['form']['selexpr']['val'] = "magnitude > 5"
    components_props['residuals']['form']['plot_type']['val'] = 'res'

    components_props['testing']['form']['gsim']['val'] = gsimnames
    components_props['testing']['form']['imt']['val'] = ['PGA', 'SA']
    components_props['testing']['form']['sa_periods']['val'] = "0.2 1.0 2.0"
    components_props['testing']['form']['selexpr']['val'] = \
        ("(magnitude > 5) & (vs30 != nan) & ((dip_1 != nan) | (dip_2 != nan)) "
         "& ((strike_1 != nan) | (strike_2 != nan)) & "
         "((rake_1 != nan) | (rake_2 != nan))")
    components_props['testing']['form']['fit_measure']['val'] = ['res',
                                                                 'lh',
                                                                 'llh',
                                                                 'mllh',
                                                                 'edr']

    # remove lines above!

    # load once the selection expression help and add a custom new
    # attribute to the forms of interest. Inject only one instance
    # because it might be relatively heavy to duplicate it for all concerned
    # fields (do it frontend side)
#     try:
#         selexpr_help = get_template('selexpr_help.html').\
#             render(dict(gmt=get_gmdb_column_desc()))
#     except TemplateDoesNotExist:
#         selexpr_help = ""

#     initdata = {'component_props': components_props,
#                 'gsims': {_[0]: _ [1:] for _ in aval_gsims(asjsonlist=True)}

    return render(request, 'egsim.html', {**_COMMON_PARAMS,
                                          'sel_component': sel_component,
                                          'components': components_tabs,
                                          'component_props': json.dumps(components_props),
                                          'gsims': json.dumps({_[0]: _ [1:] for _ in aval_gsims(asjsonlist=True)}),
                                          'server_error_message': ""})


def get_tr_models(request):
    '''Returns a JsonResponse with the data for the '''
    models = {}
    selected_model = None

    for (model, trt, geojson) in aval_trmodels(asjsonlist=True):
        if selected_model is None:
            selected_model = model
        if model not in models:
            models[model] = {}
        if trt not in models[model]:
            models[model][trt] = {'type': "FeatureCollection", 'features': []}
        models[model][trt]['features'].append(json.loads(geojson))

    return JsonResponse({'models': models, 'selected_model': selected_model},
                        safe=False)


def home(request):
    '''view for the home page (iframe in browser)'''
    return render(request, 'home.html', _COMMON_PARAMS)


def apidoc(request):
    '''view for the home page (iframe in browser)'''
    filename = 'apidoc.html'
    # get the last modified attribute to print in the document
    last_modified = None
    for tmp_ in settings.TEMPLATES:
        for dir_ in tmp_.get('DIRS', []):
            if isinstance(dir_, str) and os.path.isdir(dir_):
                path = os.path.join(dir_, filename)
                if os.path.isfile(path):
                    try:
                        last_modified = \
                            date.fromtimestamp(os.path.getmtime(path))
                        break
                    except:  #  @IgnorePep8  pylint: disable=bare-except
                        pass
    # baseurl is the base URL for the services explained in the tutorial
    # It is the request.META['HTTP_HOST'] key. But during testing, this
    # key is not present. Actually, just use a string for the moment:
    baseurl = "[eGSIM domain URL]"
    return render(request, filename,
                  dict(_COMMON_PARAMS,
                       query_params_safe_chars=QUERY_PARAMS_SAFE_CHARS,
                       last_modified=last_modified,
                       baseurl=baseurl+"/query",
                       trellis='trellis', residuals='residuals',
                       gsimsel='gsims', test='testing',
                       param=BaseForm.parnames(),
                       gmt=get_gmdb_column_desc(),
                       form_trellis=to_html_table(TrellisForm),
                       form_residuals=to_html_table(ResidualsForm),
                       form_gsims=to_html_table(GsimSelectionForm),
                       form_testing=to_html_table(TestingForm)))


def test_err(request):  # FIXME: REMOVE!!!!!
    raise ValueError('this is a test error!')


############################################################################
# eGSIM API Views:
############################################################################


class EgsimQueryViewMeta(type):
    '''metaclass for EgsimChoiceField subclasses. Populates the class attribute
    arrayfields with fields which accept array-like values. If the formclass
    is not defined, this metaclass is no-op
    '''
    def __init__(cls, name, bases, nmspc):
        super(EgsimQueryViewMeta, cls).__init__(name, bases, nmspc)
        if cls.formclass is not None:
            cls.arrayfields = set(_ for (_, f) in
                                  cls.formclass.declared_fields.items()
                                  if isinstance(f, (MultipleChoiceField,
                                                    ArrayField))
                                  )


class EgsimQueryView(View, metaclass=EgsimQueryViewMeta):
    '''base view for every eGSIM view handling data request and returning data
    in response this is usually accomplished via a form in the web page or a
    POST reqeust from the a normal query in the standard API
    '''
    formclass = None
    arrayfields = set()
    EXCEPTION_CODE = 400
    VALIDATION_ERR_MSG = 'Input validation error'

    def get(self, request):
        '''processes a get request'''
        #  get to dict:
        #  Note that percent-encoded characters are decoded automatiically
        ret = {}
        for key, values in request.GET.lists():
            newlist = []
            for val in values:
                if key in self.arrayfields and isinstance(val, str) \
                        and ',' in val:
                    newlist.extend(val.split(','))
                else:
                    newlist.append(val)
            ret[key] = newlist[0] if len(newlist) == 1 else newlist

        return self.response(ret)

    def post(self, request):
        '''processes a post request'''
        return self.response(request.body.decode('utf-8'))

    @classmethod
    def response(cls, obj):
        '''processes an input object `obj`, returning a response object.
        Calls `self.process` if the input is valid according to the Form's
        class `formclass` otherwise returns an appropriate json response with
        validation-error messages, or a json response with a gene'''
        ehm = ExceptionHandlerMiddleware
        try:
            form = cls.formclass.load(obj)
        except YAMLError as yerr:
            return ehm.jsonerr_response(yerr, code=cls.EXCEPTION_CODE)

        if not form.is_valid():
            errors = cls.format_validation_errors(form.errors)
            msg = "%s in %s" % \
                (cls.VALIDATION_ERR_MSG,
                 ', '.join(_['domain'] for _ in errors if _.get('domain', '')))
            return ehm.jsonerr_response(msg, code=cls.EXCEPTION_CODE,
                                        errors=errors)

        data = cls.process(form.cleaned_data)
        if isinstance(data, JsonResponse):
            return data
        return JsonResponse(data, safe=False)  # see GmdbPlotView.process

    @classmethod
    def process(cls, params):
        ''' core (abstract) method to be implemented in subclasses

        :param params: a dict of key-value paris which is assumed to be
            **well-formatted**: no check will be done on the dict: if the
            latter has to be validated (e.g., via a Django Form), **the
            validation should be run before this method and `params` should
            be the validated dict (e.g., as returned from `form.clean()`)**

        :return: a json-serializable object to be sent as successful response
        '''
        raise NotImplementedError()

    @classmethod
    def format_validation_errors(cls, errors):
        '''format the validation error returning the list of errors. Each
        item is a dict with keys:
             ```
             {'domain': <str>, 'message': <str>, 'code': <str>}
            ```
            :param errors: a django ErrorDict returned by the `Form.errors`
                property
        '''
        dic = json.loads(errors.as_json())
        errors = []
        for key, values in dic.items():
            for value in values:
                errors.append({'domain': key,
                               'message': value.get('message', ''),
                               'reason': value.get('code', '')})
        return errors


class TrellisView(EgsimQueryView):
    '''EgsimQueryView subclass for generating Trellis plots responses'''

    formclass = TrellisForm
    # url will be used in views. Do not end with '/':
    url = 'query/trellis'

    @classmethod
    def process(cls, params):
        return egsim_smtk.get_trellis(params)


class GsimsView(EgsimQueryView):
    '''EgsimQueryView subclass for generating Gsim selection responses'''

    formclass = GsimSelectionForm
    # url will be used in views. Do not end with '/':
    url = 'query/gsims'

    @classmethod
    def process(cls, params):
        GSIM = 'gsim'  # pylint: disable=invalid-name
        TRT = 'trt'  # pylint: disable=invalid-name
        IMT = 'imt'  # pylint: disable=invalid-name
        MODEL = 'model'  # pylint: disable=invalid-name
        LAT = 'latitude'  # pylint: disable=invalid-name
        LON = 'longitude'  # pylint: disable=invalid-name
        LAT2 = 'latitude2'  # pylint: disable=invalid-name
        LON2 = 'longitude2'  # pylint: disable=invalid-name
        tr_selector = None
        if MODEL in params or LAT in params or LON in params:
            try:
                tr_selector = TrSelector(params[MODEL], params[LON],
                                         params[LAT], params.get(LON2),
                                         params.get(LAT2))
            except KeyError:
                raise Exception('at least a tectonic regionalisation name '
                                '(model), a longitude and a '
                                'latitude must be specified')
        # return a list from the QuerySet in order to be json-serializable
        # Note that from the API, GSIM, IMT should be either provided or not
        # But from the frontend, they might be empty lists. Thus use get or
        # None:
        return list(gsim_names(params.get(GSIM) or None,
                               params.get(IMT) or None,
                               params.get(TRT) or None, tr_selector))


class GmdbPlotView(EgsimQueryView):
    '''EgsimQueryView subclass for generating Gmdb's
       magnitude vs distance plots responses'''

    formclass = GmdbPlot
    # url will be used in views. Do not end with '/':
    url = 'query/gmdbplot'

    @classmethod
    def process(cls, params):
        try:
            return egsim_smtk.get_gmdbplot(params)
        except SyntaxError as serr:
            # catch SyntaxErrors as they are most likely due to
            # selection errors, and raise appropriate Json response
            # bypassing default middleware (if installed):
            msg = 'Selection expression error: %s ("%s")' % (serr.msg,
                                                             serr.text)
            return ExceptionHandlerMiddleware.jsonerr_response(Exception(msg))
        except NameError as nerr:
            # catch SyntaxErrors as they are most likely due to
            # selection errors, and raise appropriate Json response
            # bypassing default middleware (if installed):
            msg = 'Selection expression error: "%s"' % str(nerr)
            return ExceptionHandlerMiddleware.jsonerr_response(Exception(msg))


class ResidualsView(EgsimQueryView):

    formclass = ResidualsForm
    # url will be used in views. Do not end with '/':
    url = 'query/residuals'

    @classmethod
    def process(cls, params):
        return egsim_smtk.get_residuals(params)


class TestingView(EgsimQueryView):

    formclass = TestingForm
    # url will be used in views. Do not end with '/':
    url = 'query/testing'

    @classmethod
    def process(cls, params):
        return egsim_smtk.testing(params)
