'''
Created on 17 Jan 2018

@author: riccardo
'''
import os
import io
import csv
import json
from itertools import chain, repeat

from django.http import JsonResponse
from django.http.response import HttpResponse
from django.shortcuts import render
from django.views.generic.base import View
from django.forms.fields import MultipleChoiceField
from django.conf import settings

from egsim.core.responseerrors import (exc2json, invalidform2json,
                                       requestexc2json)
from egsim.forms.forms import (TrellisForm, GsimSelectionForm, ResidualsForm,
                               GmdbPlotForm, TestingForm, FormatForm)
from egsim.core.utils import (QUERY_PARAMS_SAFE_CHARS, get_gmdb_column_desc,
                              yaml_load)
from egsim.core import smtk as egsim_smtk, figutils
from egsim.models import aval_gsims, gsim_names, TrSelector, aval_trmodels


# common parameters to be passed to any Django template:
_COMMON_PARAMS = {
    'project_name': 'eGSIM',
    'debug': settings.DEBUG,
    'data_protection_url': 'https://www.gfz-potsdam.de/en/data-protection/'
}


class KEY:  # pylint: disable=too-few-public-methods
    '''Container class (Enum-like) defining the string keys for the
    program urls/services. **Basically, each key (class attribute) [K] defines
    a menu in the web GUI navigation bar** and consequently must also have an
    associated VueJS component implemented in the directory `static/js/[k].js`.

    Each key must return an HTML reponse implemented in :func:`main`: their
    urls are implemented, as usual, in :module:`urls`.

    Additionally, some keys might be used also for defining REST API services
    (e.g., `KEY.GSIM`S, `KEY.TRELLIS`, `KEY.RESIDUALS`): their urls in this
    case are implemented **here** in the :class:URLS` because sometimes they
    must be passed in the HTML responses, too. The urls are then used in
    :module:`urls` (as usual) to call the relative :class:`RESTAPIView`
    (see below)
    '''
    HOME = 'home'
    GSIMS = 'gsims'  # pylint: disable=invalid-name
    TRELLIS = 'trellis'  # pylint: disable=invalid-name
    GMDBPLOT = 'gmdbplot'  # pylint: disable=invalid-name
    RESIDUALS = 'residuals'  # pylint: disable=invalid-name
    TESTING = 'testing'  # pylint: disable=invalid-name
    DOC = 'apidoc'  # pylint: disable=invalid-name


class TITLES:  # pylint: disable=too-few-public-methods
    '''Container class (Enum-like) of titles to be shown in the front end and
    in the documentation when talking about a service (member of the KEY class
    above)'''
    HOME = 'Home'
    GSIMS = 'Model Selection'
    TRELLIS = 'Model-to-Model Comparison'
    GMDBPLOT = 'Ground Motion Database'
    RESIDUALS = 'Model-to-Data Comparison'
    TESTING = 'Model-to-Data Testing'
    DOC = 'API Documentation'


class ICONS:  # pylint: disable=too-few-public-methods
    '''Container class (Enum-like) of icons to be shown in the front end and
    in the Home page. Strings denote the fontawesome icon name (for info see:
    https://fontawesome.bootstrapcheatsheets.com/)
    '''
    HOME = 'fa-home'
    GSIMS = 'fa-map-marker'
    TRELLIS = 'fa-area-chart'
    GMDBPLOT = 'fa-database'
    RESIDUALS = 'fa-bar-chart'
    TESTING = 'fa-list'
    DOC = 'fa-info-circle'


class URLS:  # pylint: disable=too-few-public-methods
    '''Container class (Enum-like) defining the URLS which should be injected
    into the web page (via Django) AND used in :module:`urls` for defining
    the urls and relative views.
    All URLS MUST **NOT** END WITH THE SLASH CHARACTER "/"
    '''

    # REST API URLS:
    GSIMS_RESTAPI = 'query/%s' % KEY.GSIMS
    TRELLIS_RESTAPI = 'query/%s' % KEY.TRELLIS
    RESIDUALS_RESTAPI = 'query/%s' % KEY.RESIDUALS
    TESTING_RESTAPI = 'query/%s' % KEY.TESTING
    GMDBPLOT_RESTAPI = 'query/%s' % KEY.GMDBPLOT

    # url for downloading tectonic regionalisations (GeoJson)
    GSIMS_TR = 'data/%s/tr_models' % KEY.GSIMS

    # url(s) for downloading the requests (configuration params) in json or
    # yaml. Example of a complete url:
    # DOWNLOAD_CFG/trellis/filename.json
    # (see function 'main' below and module 'urls')
    DOWNLOAD_CFG = 'data/downloadcfg'

    # urls for downloading text. Example of a complete url:
    # DOWNLOAD_ASTEXT/trellis/filename.csv
    # DOWNLOAD_ASTEXT_EU/trellis/filename.csv
    # (see function 'main' below and module 'urls')
    DOWNLOAD_ASTEXT = 'data/downloadascsv'
    DOWNLOAD_ASTEXT_EU = 'data/downloadaseucsv'

    # url for downloading as image. Note that the request body (POST data) is
    # the frontend data, in turn previously generated from one of the REST APIs
    # above: this is a bit convoluted and prevents the url to be used outside
    # the web page (all other endpoints can in principle be used as REST
    # endpoints without the web page), but we want to generate figures based on
    # what the user chooses, and also it is not always possible to convert
    # a REST API response to image (e.g., 3D grid of plots)
    DOWNLOAD_ASIMG = 'data/downloadasimage'

    # url for the frontend pages to be rendered as HTML by means of the
    # typical Django templating system: these pages are usually inside
    # <iframe>s of the web SPA (single page application)
    HOME_PAGE = 'pages/home'
    DOC_PAGE = 'pages/apidoc'


def main(request, selected_menu=None):
    '''view for the main page'''

    # Tab components (one per tab, one per activated vue component)
    # (key, label and icon) (the last is bootstrap fontawesome name)
    components_tabs = [
        (KEY.HOME, TITLES.HOME, ICONS.HOME),
        (KEY.GSIMS, TITLES.GSIMS, ICONS.GSIMS),
        (KEY.TRELLIS, TITLES.TRELLIS, ICONS.TRELLIS),
        (KEY.GMDBPLOT, TITLES.GMDBPLOT, ICONS.GMDBPLOT),
        (KEY.RESIDUALS, TITLES.RESIDUALS, ICONS.RESIDUALS),
        (KEY.TESTING, TITLES.TESTING, ICONS.TESTING),
        (KEY.DOC, TITLES.DOC, ICONS.DOC)
    ]
    # this can be changed if needed:
    sel_component = KEY.HOME if not selected_menu else selected_menu

    # properties to be passed to vuejs components.
    # If you change THE KEYS of the dict here you should change also the
    # javascript:
    components_props = {
        KEY.HOME: {
            'src': URLS.HOME_PAGE
        },
        KEY.GSIMS: {
            'form': GsimsView.formclass().to_rendering_dict(),
            'url': URLS.GSIMS_RESTAPI,
            'urls': {
                'getTectonicRegionalisations': URLS.GSIMS_TR
            }
        },
        KEY.TRELLIS: {
            'form': TrellisView.formclass().to_rendering_dict(),
            'url': URLS.TRELLIS_RESTAPI,
            'urls': {
                # the lists below must be made of elements of
                # the form [key, url]. For each element the JS library (VueJS)
                # will then create a POST data and issue a POST request
                # at the given url (see JS code for details).
                # Convention: If url is a JSON-serialized string representing
                # the dict: '{"file": <str>, "mimetype": <str>}'
                # then we will simply donwload the POST data without calling
                # the server.
                # Otherwise, when url denotes a Django view, remember
                # that the function should build a response with
                # response['Content-Disposition'] = 'attachment; filename=%s'
                # to tell the browser to download the content.
                # (it is just for safety, remember that we do not care because
                # we will download data in AJAX calls which do not care about
                # content disposition
                'downloadRequest': [
                    [
                        'json',
                        "{0}/{1}/{1}.config.json".format(URLS.DOWNLOAD_CFG,
                                                         KEY.TRELLIS)
                    ],
                    [
                        'yaml',
                        "{0}/{1}/{1}.config.yaml".format(URLS.DOWNLOAD_CFG,
                                                         KEY.TRELLIS)
                    ]
                ],
                'downloadResponse': [
                    [
                        'json',
                        '{"file": "%s.json", "mimetype": "application/json"}' %
                        KEY.TRELLIS
                    ],
                    [
                        'text/csv',
                        "{0}/{1}/{1}.csv".format(URLS.DOWNLOAD_ASTEXT,
                                                 KEY.TRELLIS)
                    ],
                    [
                        "text/csv, decimal comma",
                        "{0}/{1}/{1}.csv".format(URLS.DOWNLOAD_ASTEXT_EU,
                                                 KEY.TRELLIS)
                    ],
                ],
                'downloadImage': [
                    [
                        'png (visible plots only)',
                        "%s/%s.png" % (URLS.DOWNLOAD_ASIMG, KEY.TRELLIS)
                    ],
                    [
                        'pdf (visible plots only)',
                        "%s/%s.pdf" % (URLS.DOWNLOAD_ASIMG, KEY.TRELLIS)
                    ],
                    [
                        'eps (visible plots only)',
                        "%s/%s.eps" % (URLS.DOWNLOAD_ASIMG, KEY.TRELLIS)
                    ],
                    [
                        'svg (visible plots only)',
                        "%s/%s.svg" % (URLS.DOWNLOAD_ASIMG, KEY.TRELLIS)
                    ]
                ]
            }
        },
        KEY.GMDBPLOT: {
            'form': GmdbPlotView.formclass().to_rendering_dict(),
            'url': URLS.GMDBPLOT_RESTAPI
        },
        KEY.RESIDUALS: {
            'form': ResidualsView.formclass().to_rendering_dict(),
            'url': URLS.RESIDUALS_RESTAPI,
            'urls': {
                # download* below must be pairs of [key, url]. Each url
                # must return a
                # response['Content-Disposition'] = 'attachment; filename=%s'
                # url can also start with 'file:///' telling the frontend
                # to simply download the data
                'downloadRequest': [
                    [
                        'json',
                        "{0}/{1}/{1}.config.json".format(URLS.DOWNLOAD_CFG,
                                                         KEY.RESIDUALS)],
                    [
                        'yaml',
                        "{0}/{1}/{1}.config.yaml".format(URLS.DOWNLOAD_CFG,
                                                         KEY.RESIDUALS)
                    ],
                ],
                'downloadResponse': [
                    [
                        'json',
                        '{"file": "%s.json", "mimetype": "application/json"}' %
                        KEY.RESIDUALS
                    ],
                    [
                        'text/csv',
                        "{0}/{1}/{1}.csv".format(URLS.DOWNLOAD_ASTEXT,
                                                 KEY.RESIDUALS)
                    ],
                    [
                        "text/csv, decimal comma",
                        "{0}/{1}/{1}.csv".format(URLS.DOWNLOAD_ASTEXT_EU,
                                                 KEY.RESIDUALS)
                    ]
                ],
                'downloadImage': [
                    [
                        'png (visible plots only)',
                        "%s/%s.png" % (URLS.DOWNLOAD_ASIMG, KEY.RESIDUALS)
                    ],
                    [
                        'pdf (visible plots only)',
                        "%s/%s.pdf" % (URLS.DOWNLOAD_ASIMG, KEY.RESIDUALS)
                    ],
                    [
                        'eps (visible plots only)',
                        "%s/%s.eps" % (URLS.DOWNLOAD_ASIMG, KEY.RESIDUALS)
                    ],
                    [
                        'svg (visible plots only)',
                        "%s/%s.svg" % (URLS.DOWNLOAD_ASIMG, KEY.RESIDUALS)
                    ]
                ]
            }
        },
        KEY.TESTING: {
            'form': TestingView.formclass().to_rendering_dict(),
            'url': URLS.TESTING_RESTAPI,
            'urls': {
                # download* below must be pairs of [key, url]. Each url
                # must return a
                # response['Content-Disposition'] = 'attachment; filename=%s'
                # url can also start with 'file:///' telling the frontend
                # to simply download the data
                'downloadRequest': [
                    [
                        'json',
                        "{0}/{1}/{1}.config.json".format(URLS.DOWNLOAD_CFG,
                                                         KEY.TESTING)
                    ],
                    [
                        'yaml',
                        "{0}/{1}/{1}.config.yaml".format(URLS.DOWNLOAD_CFG,
                                                         KEY.TESTING)
                    ]
                ],
                'downloadResponse': [
                    [
                        'json',
                        '{"file": "%s.json", "mimetype": "application/json"}' %
                        KEY.TESTING
                    ],
                    [
                        'text/csv',
                        "{0}/{1}/{1}.csv".format(URLS.DOWNLOAD_ASTEXT,
                                                 KEY.TESTING)
                    ],
                    [
                        "text/csv, decimal comma",
                        "{0}/{1}/{1}.csv".format(URLS.DOWNLOAD_ASTEXT_EU,
                                                 KEY.TESTING)
                    ]
                ]
            }
        },
        KEY.DOC: {
            'src': URLS.DOC_PAGE
        }
    }

    # Yes, what we are about to do it's really bad practice. But when in debug
    # mode, we want to easily test the frontend with typical configurations
    # already setup. In production, we will not enter here:
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
        testingformdict['gsim']['val'] = gsimnames + ['AbrahamsonSilva2008']
        testingformdict['imt']['val'] = ['PGA', 'PGV']
        testingformdict['sa_period']['val'] = "0.2 1.0 2.0"

        components_props['testing']['form']['fit_measure']['val'] = ['res',
                                                                     'lh',
                                                                     # 'llh',
                                                                     # 'mllh',
                                                                     # 'edr'
                                                                     ]

    # setup browser detection
    allowed_browsers = [['Chrome', 49], ['Firefox', 45], ['Safari', 10]]
    invalid_browser_message = ('Some functionalities might not work '
                               'correctly. In case, please use any of the '
                               'following tested browsers: %s' %
                               ', '.join('%s &ge; %d' % (brw, ver)
                                         for brw, ver in allowed_browsers))

    gsims = json.dumps({_[0]: _[1:] for _ in aval_gsims(asjsonlist=True)})
    return render(request,
                  'egsim.html',
                  {
                      **_COMMON_PARAMS,
                      'sel_component': sel_component,
                      'components': components_tabs,
                      'component_props': json.dumps(components_props),
                      'gsims': gsims,
                      'allowed_browsers': allowed_browsers,
                      'invalid_browser_message': invalid_browser_message
                  }
                  )


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
    egsim_data = {
        'GSIMS': {
            'title': TITLES.GSIMS,
            'icon': ICONS.GSIMS
        },
        'TRELLIS': {
            'title': TITLES.TRELLIS,
            'icon': ICONS.TRELLIS
        },
        'GMDB': {
            'title': TITLES.GMDBPLOT,
            'icon': ICONS.GMDBPLOT
        },
        'RESIDUALS': {
            'title': TITLES.RESIDUALS,
            'icon': ICONS.RESIDUALS
        },
        'TESTING': {
            'title': TITLES.TESTING,
            'icon': ICONS.TESTING
        }
    }
    return render(request, 'home.html', dict(_COMMON_PARAMS,
                                             egsim_data=egsim_data,
                                             info_str=('Version 1.0.2, '
                                                       'last updated: '
                                                       'September 2019')))


def apidoc(request):
    '''view for the home page (iframe in browser)'''
    filename = 'apidoc.html'
    # baseurl is the base URL for the services explained in the tutorial
    # It is the request.META['HTTP_HOST'] key. But during testing, this
    # key is not present. Actually, just use a string for the moment:
    baseurl = "<eGSIMsite>"
    # Note that the keus of the egsim_data dict below should NOT
    # be changed: if you do, you should also change the templates
    egsim_data = {
        'GSIMS': {
            'title': TITLES.GSIMS,
            'path': URLS.GSIMS_RESTAPI,
            'form': GsimsView.formclass().to_rendering_dict(False),
            'key': KEY.GSIMS
        },
        'TRELLIS': {
            'title': TITLES.TRELLIS,
            'path': URLS.TRELLIS_RESTAPI,
            'form': TrellisView.formclass().to_rendering_dict(False),
            'key': KEY.TRELLIS
        },
        'RESIDUALS': {
            'title': TITLES.RESIDUALS,
            'path': URLS.RESIDUALS_RESTAPI,
            'form': ResidualsView.formclass().to_rendering_dict(False),
            'key': KEY.RESIDUALS
        },
        'TESTING': {
            'title': TITLES.TESTING,
            'path': URLS.TESTING_RESTAPI,
            'form': TestingView.formclass().to_rendering_dict(False),
            'key': KEY.TESTING
        },
        'FORMAT': {
            'form': FormatForm().to_rendering_dict(False)
        }
    }

    return render(request, filename,
                  dict(_COMMON_PARAMS,
                       query_params_safe_chars=QUERY_PARAMS_SAFE_CHARS,
                       egsim_data=egsim_data,
                       baseurl=baseurl,
                       gmt=get_gmdb_column_desc(),
                       )
                  )


def imprint(request):
    return render(request, 'imprint.html', {
        'data_protection_url': _COMMON_PARAMS['data_protection_url']
    })


def download_request(request, key, filename):
    '''Returns the request (configuration) re-formatted according to the syntax
    inferred from filename (*.json or *.yaml) to be downloaded by the front
    end GUI.

    :param key: string in [KEY.TRELLIS, KEY.RESIDUALS, KEY.TESTING]
    '''
    formclass = _key2view(key).formclass
    inputdict = yaml_load(request.body.decode('utf-8'))
    dataform = formclass(data=inputdict)  # pylint: disable=not-callable
    if not dataform.is_valid():
        return invalidform2json(dataform)
    buffer = io.StringIO()
    ext_nodot = os.path.splitext(filename)[1][1:].lower()
    dataform.dump(buffer, syntax=ext_nodot)
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


def download_astext(request, key, filename, text_sep=',', text_dec='.'):
    '''Returns the text/csv data to be downloaded by the front end GUI.
    The request's body is the JSON data resulting from a previous
    call of the GET or POST method of any these
    views: TrellisView, ResidualsView, TestingView.

    :param key: string in [KEY.TRELLIS, KEY.RESIDUALS, KEY.TESTING]
    '''
    viewclass = _key2view(key)
    inputdict = yaml_load(request.body.decode('utf-8'))
    response = viewclass.response_text(inputdict, text_sep, text_dec)
    response['Content-Disposition'] = 'attachment; filename=%s' % filename
    return response


def _key2view(key):
    '''maps a key (string) in [KEY.TRELLIS, KEY.RESIDUALS, KEY.TESTING] to
    the relative :class:`RESTAPIView` subclass defined in this module
    '''
    return {
        KEY.TRELLIS: TrellisView,
        KEY.RESIDUALS: ResidualsView,
        KEY.TESTING: TestingView
    }[key]


def download_asimage(request, filename):
    '''Returns the image from the given request built in the frontend GUI
    according to the choosen plots
    '''
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
    '''Stupid function raiseing for front end test purposes. Might be removed
    soon'''
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
                                  if isinstance(f, (MultipleChoiceField,))
                                  )


class RESTAPIView(View, metaclass=EgsimQueryViewMeta):
    '''base view for every eGSIM REST API endpoint
    '''
    formclass = None
    arrayfields = set()

    def get(self, request):
        '''processes a get request'''
        try:
            #  get to dict:
            #  Note that percent-encoded characters are decoded automatiically
            ret = {}
            # https://docs.djangoproject.com/en/2.2/ref/request-response/#django.http.QueryDict.lists
            for key, values in request.GET.lists():
                if key in self.arrayfields:
                    newvalues = []
                    for val in values:
                        newvalues.extend(val.split(','))
                    ret[key] = newvalues
                else:
                    ret[key] = values[0] if len(values) == 1 else values
            return self.response(ret)

        except Exception as err:  # pylint: disable=broad-except
            return requestexc2json(err)

    def post(self, request):
        '''processes a post request'''
        try:
            return self.response(yaml_load(request.body.decode('utf-8')))
        except Exception as err:  # pylint: disable=broad-except
            return requestexc2json(err)

    @classmethod
    def response(cls, inputdict):
        '''processes an input dict `inputdict`, returning a response object.
        Calls `self.process` if the input is valid according to
        `cls.formclass`. On error, returns an appropriate json response
        (see `module`:core.responseerrors)
        '''
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

        # calculate the content length. This has to be done before creating
        # the response as it might be that the latter closes the buffer. It
        # is questionable then to use a buffer (we might use getvalue() on it
        # but we pospone this check ...
        buffer.seek(0, os.SEEK_END)
        contentlength = buffer.tell()
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='text/csv')
        response['Content-Length'] = str(contentlength)
        return response

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
        # print standard deviations. Do it once for all at the end as we think
        # it might be easier for a user using Excel or LibreOffice, than having
        # each gsim with 'yvalues and 'stdvalues' next to each other
        for imt in process_result['imts']:
            imt_objs = process_result[imt]
            for obj in imt_objs:
                mag, dist, vs30, ylabel = obj['magnitude'], obj['distance'],\
                    obj['vs30'], obj['stdlabel']
                for gsim, values in obj['stdvalues'].items():
                    # the dict we are iterating might be empty: in case
                    # do not print anything
                    yield chain([imt, gsim, mag, dist, vs30, ylabel], values)


class GmdbPlotView(RESTAPIView):  # pylint: disable=abstract-method
    '''EgsimQueryView subclass for generating Gmdb's
       magnitude vs distance plots responses'''

    formclass = GmdbPlotForm

    @classmethod
    def process(cls, inputdict):
        return egsim_smtk.get_gmdbplot(inputdict)


class ResidualsView(RESTAPIView):
    '''EgsimQueryView subclass for generating Residuals plot responses'''

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
    '''EgsimQueryView subclass for generating Testing responses'''

    formclass = TestingForm

    @classmethod
    def process(cls, inputdict):
        return egsim_smtk.testing(inputdict)

    @classmethod
    def to_rows(cls, process_result):
        fitmeasures = process_result['Measure of fit']
        dbrecords = process_result['Db records']
        yield ['measure of fit', 'imt', 'gsim', 'value', 'db records used']
        for mof, mofs in fitmeasures.items():
            for imt, imts in mofs.items():
                for gsim, value in imts.items():
                    yield [mof, imt, gsim, value, dbrecords[gsim]]
