'''
Created on 17 Jan 2018

@author: riccardo
'''
import os
import io
import csv
import json
import re
from datetime import date
from itertools import chain, repeat

from yaml.error import YAMLError

from django.http import JsonResponse
from django.http.response import HttpResponse
from django.shortcuts import render
from django.views.generic.base import View
from django.forms.fields import MultipleChoiceField
from django.conf import settings

from egsim.core.responseerrors import exc2json, invalidform2json
from egsim.forms.forms import (TrellisForm, GsimSelectionForm, ResidualsForm,
                               GmdbPlotForm, TestingForm, FormatForm)
from egsim.core.utils import (QUERY_PARAMS_SAFE_CHARS, get_gmdb_column_desc,
                              yaml_load)
from egsim.core import smtk as egsim_smtk
from egsim.forms.fields import ArrayField
from egsim.models import aval_gsims, gsim_names, TrSelector, aval_trmodels


# common parameters to be passed to any Django template:
_COMMON_PARAMS = {
    'project_name': 'eGSIM',
    'debug': settings.DEBUG,
}


class KEY:
    '''Container class (enum-like) defining the string keys for the program
    urls/services. Each string should be unique and
    associated to a menu in the frontend (see `main`),
    and optionally to a URL in the REST API (see the module 'urls' and
    `api_url`).
    A new key here in principle should be associated to some modification
    in `main` and/or the module 'urls'.
    '''
    HOME = 'home'
    GSIMS = 'gsims'  # pylint: disable=invalid-name
    TRELLIS = 'trellis'  # pylint: disable=invalid-name
    GMDB = 'gmdbplot'  # pylint: disable=invalid-name
    RES = 'residuals'  # pylint: disable=invalid-name
    TEST = 'testing'  # pylint: disable=invalid-name
    DOC = 'apidoc'  # pylint: disable=invalid-name


def api_url(urlkey):
    '''Builds a query from the given urlkey (string)
    This function should be used as central point where we define the eGSIM
    query API urls, so that it can be changed in a single place.
    Currently, it appends `urlkey` (stripped tiwh ending slashes, if any) to
    'query/'
    '''
    return "query/%s" % re.sub(r'/+$', '',  urlkey)


def main(request, selected_menu=None):
    '''view for the main page'''

    # Tab components (one per tab, one per activated vue component)
    # (key, label and icon) (the last is bootstrap fontawesome name)
    components_tabs = [(KEY.HOME, 'Home', 'fa-home'),
                       (KEY.GSIMS, 'Gsim selection', 'fa-map-marker'),
                       (KEY.TRELLIS, 'Trellis Plots', 'fa-area-chart'),
                       (KEY.GMDB, 'Ground Motion database', 'fa-database'),
                       (KEY.RES, 'Residuals', 'fa-bar-chart'),
                       (KEY.TEST, 'Testing', 'fa-list'),
                       (KEY.DOC, 'API Documentation', 'fa-info-circle')]
    # this can be changed if needed:
    sel_component = KEY.HOME if not selected_menu else selected_menu

    # properties to be passed to vuejs components:
    components_props = {
        KEY.HOME: {'src': 'pages/home'},
        KEY.GSIMS: {'tr_models_url': 'data/tr_models',
                    'url': api_url(KEY.GSIMS),
                    'form': GsimsView.formclass().to_rendering_dict()},
        KEY.TRELLIS: {'url': api_url(KEY.TRELLIS),
                      'form': TrellisView.formclass().to_rendering_dict()},
        KEY.GMDB: {'url': api_url(KEY.GMDB),
                   'form': GmdbPlotView.formclass().to_rendering_dict()},
        KEY.RES: {'url': api_url(KEY.RES),
                  'form': ResidualsView.formclass().to_rendering_dict()},
        KEY.TEST: {'url': api_url(KEY.TEST),
                   'form': TestingView.formclass().to_rendering_dict()},
        KEY.DOC: {'src': 'pages/apidoc'}
    }

    # REMOVE LINES BELOW!!!
    if settings.DEBUG:
        gsimnames = ['AkkarEtAlRjb2014', 'BindiEtAl2014Rjb', 'BooreEtAl2014',
                     'CauzziEtAl2014']
        trellisformdict = components_props['trellis']['form']
        trellisformdict['gsim']['val'] = gsimnames
        trellisformdict['imt']['val'] = ['PGA']
        trellisformdict['magnitude']['val'] = "5:7"
        trellisformdict['distance']['val'] = "10 50 100"
        trellisformdict['aspect']['val'] = 1
        trellisformdict['dip']['val'] = 60
        trellisformdict['plot_type']['val'] = 's'

        residualsformdict = components_props['residuals']['form']
        residualsformdict['gsim']['val'] = gsimnames
        residualsformdict['imt']['val'] = ['PGA', 'SA']
        residualsformdict['sa_period']['val'] = "0.2 1.0 2.0"
        residualsformdict['selexpr']['val'] = "magnitude > 5"
        residualsformdict['plot_type']['val'] = 'res'

        testingformdict = components_props['testing']['form']
        testingformdict['gsim']['val'] = gsimnames
        testingformdict['imt']['val'] = ['PGA', 'SA']
        testingformdict['sa_period']['val'] = "0.2 1.0 2.0"

        components_props['testing']['form']['fit_measure']['val'] = ['res',
                                                                     'lh',
                                                                     'llh',
                                                                     'mllh',
                                                                     'edr']

    # remove lines above!
    gsims = json.dumps({_[0]: _[1:] for _ in aval_gsims(asjsonlist=True)})
    return render(request, 'egsim.html',
                  {**_COMMON_PARAMS,
                   'sel_component': sel_component,
                   'components': components_tabs,
                   'component_props': json.dumps(components_props),
                   'gsims': gsims,
                   'server_error_message': ""})


def get_tr_models(request):  # pylint: disable=unused-argument
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
    # baseurl is the base URL for the services explained in the tutorial
    # It is the request.META['HTTP_HOST'] key. But during testing, this
    # key is not present. Actually, just use a string for the moment:
    baseurl = "[eGSIM domain URL]"
    form = {
        KEY.GSIMS: GsimsView.formclass().to_rendering_dict(False),
        KEY.TRELLIS: TrellisView.formclass().to_rendering_dict(False),
        KEY.GMDB: GmdbPlotView.formclass().to_rendering_dict(False),
        KEY.RES: ResidualsView.formclass().to_rendering_dict(False),
        KEY.TEST: TestingView.formclass().to_rendering_dict(False),
        'format': FormatForm().to_rendering_dict(False)
    }
    return render(request, filename,
                  dict(_COMMON_PARAMS,
                       form=form,
                       query_params_safe_chars=QUERY_PARAMS_SAFE_CHARS,
                       baseurl=baseurl+"/query",
                       trellis='trellis', residuals='residuals',
                       gsimsel='gsims', test='testing',
                       gmt=get_gmdb_column_desc(),
                       )
                  )


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


def download_request(request, filename, formclass):
    '''Returns the request re-formatted according to the given syntax.
    Uses request.body so this method should be called from a POST request
    '''
    inputdict = yaml_load(request.body.decode('utf-8'))
    dataform = formclass(data=inputdict)  # pylint: disable=not-callable
    if not dataform.is_valid():
        return invalidform2json(dataform)
    buffer = io.StringIO()
    ext = os.path.splitext(filename)[1].lower()
    if ext[:1] == '.':
        ext = ext[1:]
    dataform.dump(buffer, syntax=ext)
    buffer.seek(0)
    if ext == 'json':
        response = HttpResponse(buffer, content_type='application/json')
    else:
        response = HttpResponse(buffer, content_type='application/x-yaml')
    response['Content-Disposition'] = 'attachment; filename=%s' % filename
    return response


class RESTAPIView(View, metaclass=EgsimQueryViewMeta):
    '''base view for every eGSIM view handling data request and returning data
    in response this is usually accomplished via a form in the web page or a
    POST reqeust from the a normal query in the standard API
    '''
    formclass = None
    arrayfields = set()
    extensions = {
        'json': 'json',
        'text': 'csv'
    }

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
        try:
            return self.response(yaml_load(request.body.decode('utf-8')))
        except YAMLError as yerr:
            return exc2json(yerr)

    @classmethod
    def response(cls, inputdict):
        '''processes an input dict `inputdict`, returning a response object.
        Calls `self.process` if the input is valid according to the Form's
        class `formclass` otherwise returns an appropriate json response with
        validation-error messages, or a json response with a gene'''
        filename = inputdict.pop('filename', '')
        formatform = FormatForm(inputdict)
        if not formatform.is_valid():
            return invalidform2json(formatform)
        formatdict = formatform.cleaned_data

        for key in formatdict:
            inputdict.pop(key, None)
        dataform = cls.formclass(data=inputdict)  # pylint: disable=not-callable
        if not dataform.is_valid():
            return invalidform2json(dataform)

        outputdict = cls.process(dataform.cleaned_data)
        frmt = formatdict['format'].lower()
        try:
            if frmt == 'json':
                response = cls.response_json(outputdict)
            else:
                response = cls.response_text(outputdict,
                                             formatdict.get('text_sep', ','),
                                             formatdict.get('text_dec', '.'))
        except NotImplementedError:
            return exc2json('format "%s" is not currently implemented' % frmt)

        if filename:
            fname, ext = os.path.splitext(filename)
            if not ext:
                filename = "%s.%s" % (fname, cls.extensions[frmt])
            response['Content-Disposition'] = \
                'attachment; filename=%s' % filename
        return response

    @classmethod
    def response_json(cls, process_result):
        '''Returns a JSON response

        :param process_result: the output of `self.process`
        '''
        return JsonResponse(process_result, safe=False)

    @classmethod
    def response_text(cls, process_result, text_sep=',', text_dec='.'):
        '''Returns a text/csv response

        :param process_result: the output of `self.process`
        '''
        # code copied from: https://stackoverflow.com/a/41706831
        buffer = io.StringIO()  # python 2 needs io.BytesIO() instead
        wrt = csv.writer(buffer,
                         delimiter=text_sep,
                         quotechar='"',
                         quoting=csv.QUOTE_MINIMAL)
        # From the docs:
        # The value None is written as the empty string.
        # All non-string data are stringified with str() before being written.

        # first build a list to get the maximum number of columns (for safety):
        rowsaslist = []
        maxcollen = 0
        comma_decimal = text_dec == ','
        for row in cls.to_rows(process_result):
            if comma_decimal:
                row = cls.convert_to_comma_as_decimal(row)
            rowsaslist.append(row if hasattr(row, '__len__') else list(row))
            maxcollen = max(maxcollen, len(rowsaslist[-1]))

        wrt.writerows(chain(r, repeat(None, maxcollen-len(r)))
                      for r in rowsaslist)
        buffer.seek(0)
        return HttpResponse(buffer, content_type='text/csv')

    @classmethod
    def convert_to_comma_as_decimal(cls, row):
        '''Creates a generator yielding each element of row where numeric
        values are converted to strings with comma as decimal separator.
        For non-float values, each row element is yielded as it is

        @param rows: a list of lists
        '''
        for cell in row:
            if isinstance(cell, float):
                yield str(cell).replace('.', ',')
            else:
                yield cell

    @classmethod
    def process(cls, inputdict):
        ''' core (abstract) method to be implemented in subclasses

        :param inputdict: a dict of key-value pairs of input parameters, which
            **is assumed to have been already validated via this.formclass()**
            (thus no check is needed)

        :return: a json-serializable object to be sent as successful response
        '''
        raise NotImplementedError()

    @classmethod
    def to_rows(cls, process_result):
        '''Abstract-like optional method to be implemented in subclasses.
        Converts the input argument into an iterable of rows, where each
        row is in turn an iterable of strings representing "cell" values:
        the resulting output is in fact intended to be the input for
        text/csv formatted responses.
        Any code calling this method should not rely on all yielded rows
        having the same number of elements (see e.g.
        `self.response_text` where rows are padded with empty values).

        :param process_result: the output of `self.process`
        '''
        raise NotImplementedError()


class GsimsView(RESTAPIView):
    '''EgsimQueryView subclass for generating Gsim selection responses'''

    formclass = GsimSelectionForm

    @classmethod
    def process(cls, inputdict):
        GSIM = 'gsim'  # pylint: disable=invalid-name
        TRT = 'trt'  # pylint: disable=invalid-name
        IMT = 'imt'  # pylint: disable=invalid-name
        MODEL = 'model'  # pylint: disable=invalid-name
        LAT = 'latitude'  # pylint: disable=invalid-name
        LON = 'longitude'  # pylint: disable=invalid-name
        LAT2 = 'latitude2'  # pylint: disable=invalid-name
        LON2 = 'longitude2'  # pylint: disable=invalid-name
        tr_selector = None
        if MODEL in inputdict or LAT in inputdict or LON in inputdict:
            try:
                tr_selector = TrSelector(inputdict[MODEL], inputdict[LON],
                                         inputdict[LAT], inputdict.get(LON2),
                                         inputdict.get(LAT2))
            except KeyError:
                raise Exception('at least a tectonic regionalisation name '
                                '(model), a longitude and a '
                                'latitude must be specified')
        # return a list from the QuerySet in order to be json-serializable
        # Note that from the API, GSIM, IMT should be either provided or not
        # But from the frontend, they might be empty lists. Thus use get or
        # None:
        return list(gsim_names(inputdict.get(GSIM), inputdict.get(IMT),
                               inputdict.get(TRT), tr_selector))

    @classmethod
    def to_rows(cls, process_result):
        return [[str(_)] for _ in process_result]


class TrellisView(RESTAPIView):
    '''EgsimQueryView subclass for generating Trellis plots responses'''

    formclass = TrellisForm

    @classmethod
    def process(cls, inputdict):
        return egsim_smtk.get_trellis(inputdict)

    @classmethod
    def to_rows(cls, process_result):

        yield ['imt', 'gsim', 'magnitude', 'distance', 'vs30']
        yield chain(repeat('', 5), [process_result['xlabel']],
                    process_result['xvalues'])
        for imt in process_result['imts']:
            imt_objs = process_result[imt]
            for obj in imt_objs:
                mag, dist, vs30, ylabel = obj['magnitude'], obj['distance'],\
                    obj['vs30'], obj['ylabel']
                for gsim, values in obj['yvalues'].items():
                    yield chain([imt, gsim, mag, dist, vs30, ylabel], values)


class GmdbPlotView(RESTAPIView):  # pylint: disable=abstract-method
    '''EgsimQueryView subclass for generating Gmdb's
       magnitude vs distance plots responses'''

    formclass = GmdbPlotForm

    @classmethod
    def process(cls, inputdict):
        return egsim_smtk.get_gmdbplot(inputdict)


class ResidualsView(RESTAPIView):

    formclass = ResidualsForm

    @classmethod
    def process(cls, inputdict):
        return egsim_smtk.get_residuals(inputdict)

    @classmethod
    def to_rows(cls, process_result):
        stats = egsim_smtk.RESIDUALS_STATS
        yield chain(['imt', 'type', 'gsim'], stats)
        for imt, imts in process_result.items():
            for type_, types in imts.items():
                for gsim, res_plot in types.items():
                    yield chain([imt, type_, gsim],
                                (res_plot[stat] for stat in stats),
                                [res_plot['xlabel']], res_plot['xvalues'])
                    yield chain(repeat('', 9), [res_plot['ylabel']],
                                res_plot['yvalues'])


class TestingView(RESTAPIView):

    formclass = TestingForm

    @classmethod
    def process(cls, inputdict):
        return egsim_smtk.testing(inputdict)

    @classmethod
    def to_rows(cls, process_result):
        fitmeasures = process_result['Measure of fit']
        dbrecords = process_result['Db records']
        yield ['measure of fit', 'imt', 'gsim', 'db records', 'value']
        for mof, mofs in fitmeasures.items():
            for imt, imts in mofs.items():
                for gsim, value in imts.items():
                    yield [mof, imt, gsim, dbrecords[gsim], value]
