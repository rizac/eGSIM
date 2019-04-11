'''
Created on 17 Jan 2018

@author: riccardo
'''
import os
import json
from collections import OrderedDict
from datetime import date
import inspect

from yaml.error import YAMLError

from django.http import JsonResponse
from django.shortcuts import render
# from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import View
from django.conf import settings

from egsim.middlewares import ExceptionHandlerMiddleware
from egsim.forms.forms import TrellisForm, GsimSelectionForm, GmdbForm, ResidualsForm, BaseForm
from egsim.core.utils import EGSIM, QUERY_PARAMS_SAFE_CHARS
from egsim.core import smtk as egsim_smtk
from egsim.forms.fields import ArrayField
from egsim.models import aval_gsims, gsim_names, TrSelector, aval_trmodels
from django.forms.fields import MultipleChoiceField


_COMMON_PARAMS = {
    'project_name': 'eGSIM',
    'debug': settings.DEBUG,
    'menus': OrderedDict([('home', 'Home'), ('trsel', 'Gsim selection'),
                          ('trellis', 'Trellis plots'),
                          ('gmdb', 'Ground Motion database'),
                          ('residuals', 'Residuals'),
                          ('apidoc', 'API documentation'),]),
    }

# def index(request):
#     '''view for the index page. Defaults to the main view with menu="home"'''
#     return render(request, 'index.html', dict(_COMMON_PARAMS, menu='home'))


def main(request, menu):
    '''view for the main page'''
    return render(request, 'index.html', dict(_COMMON_PARAMS, menu=menu))


def home(request):
    '''view for the home page (iframe in browser)'''
    return render(request, 'home.html', _COMMON_PARAMS)


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
                        last_modified = date.fromtimestamp(os.path.getmtime(path))
                        break
                    except:  #  @IgnorePep8  pylint: disable=bare-except
                        pass
    return render(request, filename, dict(_COMMON_PARAMS,
                                          query_params_safe_chars=QUERY_PARAMS_SAFE_CHARS,
                                          last_modified=last_modified,
                                          baseurl=request.META['HTTP_HOST']+"/query",
                                          trellis='trellis', residuals='residuals',
                                          gsimsel='gsims', test='testing',
                                          param=BaseForm.parnames(),
                                          form_trellis=TrellisForm.toHTML(),
                                          form_residuals=ResidualsForm.toHTML(),
                                          form_gsims=GsimSelectionForm.toHTML()))

def trsel(request):
    '''view returing the page forfor the gsim tectonic region
    selection'''
    return render(request, 'trsel.html', dict(_COMMON_PARAMS, post_url='../query/gsims'))


def trellis(request):
    '''view for the trellis page (iframe in browser)'''
    return render(request, 'trellis.html', dict(_COMMON_PARAMS, form=TrellisForm(),
                                                post_url='../query/trellis'))


def get_gmdbs(request):
    '''view for the residuals page (iframe in browser)'''
    return JsonResponse({'avalgmdbs': EGSIM.gmdb_names(),
                         'selectedgmdb': next(iter(EGSIM.gmdb_names()))},
                        safe=False)


def gmdb(request):
    '''view for the residuals page (iframe in browser)'''
    return render(request, 'gmdb.html', dict(_COMMON_PARAMS, form=GmdbForm(),
                                             post_url='../query/gmdbplot'))


def residuals(request):
    '''view for the residuals page (iframe in browser)'''
    return render(request, 'residuals.html', dict(_COMMON_PARAMS, form=ResidualsForm(),
                                                  post_url='../query/residuals'))


def loglikelihood(request):
    '''view for the log-likelihood page (iframe in browser)'''
    return render(request, 'loglikelihood.html', _COMMON_PARAMS)


# @api_view(['GET', 'POST'])
def get_init_params(request):  # @UnusedVariable pylint: disable=unused-argument
    """
    Returns input parameters for input selection. Called when app initializes
    """
    return JsonResponse(aval_gsims(asjsonlist=True), safe=False)


class EgsimQueryViewMeta(type):
    '''metaclass for EgsimChoiceField subclasses. Takes the class attribute _base_choices
    and modifies it into a valid `choices` argument, and creates the dict `cls._mappings`
    See :class:`EgsimChoiceField` documentation for details'''
    def __init__(cls, name, bases, nmspc):
        super(EgsimQueryViewMeta, cls).__init__(name, bases, nmspc)
        if cls.formclass is not None:
            cls.arrayfields = set(_ for (_, f) in cls.formclass.declared_fields.items()
                                  if isinstance(f, (MultipleChoiceField, ArrayField)))


class EgsimQueryView(View, metaclass=EgsimQueryViewMeta):
    '''base view for every eGSIM view handling data request and returning data in response
    this is usually accomplished via a form in the web page or a POST reqeust from
    the a normal query in the standard API'''

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
                if key in self.arrayfields and isinstance(val, str) and ',' in val:
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
        Calls `self.process` if the input is valid according to the Form's class `formclass`
        otherwise returns an appropriate json response with validation-error messages,
        or a json response with a gene'''
        try:
            form = cls.formclass.load(obj)
        except YAMLError as yerr:
            return ExceptionHandlerMiddleware.jsonerr_response(yerr, code=cls.EXCEPTION_CODE)

        if not form.is_valid():
            errors = cls.format_validation_errors(form.errors)
            msg = "%s in %s" % \
                (cls.VALIDATION_ERR_MSG,
                 ', '.join(_['domain'] for _ in errors if _.get('domain', '')))
            return ExceptionHandlerMiddleware.jsonerr_response(msg,
                                                               code=cls.EXCEPTION_CODE,
                                                               errors=errors)

        return JsonResponse(cls.process(form.cleaned_data), safe=False)

    @classmethod
    def process(cls, params):
        ''' core (abstract) method to be implemented in subclasses

        :param params: a dict of key-value paris which is assumed to be **well-formatted**:
            no check will be done on the dict: if the latter has to be validated (e.g., via
            a Django Form), **the validation should be run before this method and `params`
            should be the validated dict (e.g., as returned from `form.clean()`)**

        :return: a json-serializable object to be sent as successful response
        '''
        raise NotImplementedError()

    @classmethod
    def format_validation_errors(cls, errors):
        '''format the validation error returning the list of errors. Each item is a dict with
        keys:
             ```
             {'domain': <str>, 'message': <str>, 'code': <str>}
            ```
            :param errors: a django ErrorDict returned by the `Form.errors` property
        '''
        dic = json.loads(errors.as_json())
        errors = []
        for key, values in dic.items():
            for value in values:
                errors.append({'domain': key, 'message': value.get('message', ''),
                               'reason': value.get('code', '')})
        return errors


class TrellisView(EgsimQueryView):
    '''EgsimQueryView subclass for generating Trelli plots responses'''

    formclass = TrellisForm

    @classmethod
    def process(cls, params):
        return egsim_smtk.get_trellis(params)


class GsimsView(EgsimQueryView):

    formclass = GsimSelectionForm

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
                tr_selector = TrSelector(params[MODEL], params[LON], params[LAT],
                                         params.get(LON2), params.get(LAT2))
            except KeyError:
                raise Exception('at least a tectonic regionalisation name '
                                '(model), a longitude and a '
                                'latitude must be specified')
        # return a list from the QuerySet in order to be json-serializable
        return list(gsim_names(params.get(GSIM), params.get(IMT),
                               params.get(TRT), tr_selector))


class GmdbPlotView(EgsimQueryView):

    formclass = GmdbForm

    @classmethod
    def process(cls, params):
        return egsim_smtk.get_gmdbplot(params)


class ResidualsView(EgsimQueryView):

    formclass = ResidualsForm

    @classmethod
    def process(cls, params):
        return egsim_smtk.get_residuals(params)


# TESTS (FIXME: REMOVE?) #####################################################################

def test_err(request):
    raise ValueError('this is a test error!')


def test(request):
    '''view for the trellis (test) page (iframe in browser)'''
    err = ""
    comps = MENUS
    components_props = {}
    clear_choices = ['gsim', 'imt']
    for comp in comps:
        name, data = comp[0], dict(comp[-1])
        form = data.get('form', None)
        if isinstance(form, BaseForm):
            formdata = form.to_rendering_dict()
            # for perf reasons, remove the choices from the field 'clear_choices':
            for field in clear_choices:
                if field in formdata:
                    formdata[field]['choices'] = []
            data['form'] = formdata

        components_props[name] = data

    # REMOVE THESE LINES!!!
    components_props['trellis']['form']['gsim']['val'] = ['AbrahamsonEtAl2014']
    components_props['trellis']['form']['imt']['val'] = ['PGA']
    components_props['trellis']['form']['magnitude']['val'] = "3:4"
    components_props['trellis']['form']['distance']['val'] = "0:1:100"
    components_props['trellis']['form']['aspect']['val'] = 1
    components_props['trellis']['form']['dip']['val'] = 60


    initdata = {'component_props': components_props,
                'gsims': aval_gsims(asjsonlist=True)}

    return render(request, 'egsim.html', {'sel_component': comps[1][0],
                                          'components': [_[:3] for _ in comps],
                                          'initdata': json.dumps(initdata),
                                          'server_error_message': err,
                                          'debug': settings.DEBUG})


from django.conf.urls import url

APIS = [
    url(r'^query/gsims/?$', GsimsView.as_view(), name='gsims'),
    url(r'^query/trellis/?$', TrellisView.as_view(), name='trellis'),
    url(r'^query/gmdbplot/?$', GmdbPlotView.as_view(), name='gmdbplot'),
    url(r'^query/residuals/?$', ResidualsView.as_view(), name='residuals'),
    url(r'^query/testing/?$', ResidualsView.as_view(), name='testing'),
]

# menus is an array of menus in the top panel of the main page
# the elements have [url of the page, Name of the menu, url of the form submission]
# where the last element might be empty (in that case the page us static
# and the url of the first element will be shown in an iframe)
MENUS = [
    ('home', 'Home', 'fa-home', {'src': 'service/home'}),
    ('gsims', 'Gsim selection', 'fa-map-marker', {'url': 'query/gsims',
                                                  'tr_models_url': 'data/tr_models',
                                                  'form': GsimSelectionForm()}),
    ('trellis', 'Trellis Plots', 'fa-area-chart', {'url': 'query/trellis',
                                                   'form': TrellisForm()}),
    ('gmdbplot', 'Ground Motion database', 'fa-database', {'url': 'query/gmdbplot',
                                                           'form': GmdbForm()}),
    ('residuals', 'Residuals', 'fa-bar-chart', {'url': 'query/residuals',
                                                'form': ResidualsForm()}),
    ('testing', 'Testing', 'fa-list', {'url': 'query/testing',
                                       'form': {}}),
    ('apidoc', 'API Documentation', 'fa-info-circle', {'src': 'service/apidoc'})
    ]


