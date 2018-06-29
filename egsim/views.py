'''
Created on 17 Jan 2018

@author: riccardo
'''
import os
import json
from collections import OrderedDict

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
# from django.urls import reverse
# from django.http.response import HttpResponseRedirect
# from django.conf import settings
# from django.views.decorators.http import require_http_methods
# from rest_framework.decorators import api_view
# from rest_framework.response import Response

# from openquake.hazardlib.gsim import get_available_gsims

# import smtk.trellis.trellis_plots as trpl
# import smtk.trellis.configure as rcfg

from egsim.forms import TrellisForm, BaseForm
from egsim.core.trellis import compute_trellis
from django.forms.utils import ErrorDict
from django.views.generic.base import View
from egsim.core import yaml_load


# FIXME: very hacky to parse the form for defaults, is it there a better choice?
_COMMON_PARAMS = {
    'project_name': 'eGSIM',
    'debug': True,
    'menus': OrderedDict([('home', 'Home'), ('trellis', 'Trellis plots'),
                          ('residuals', 'Residuals'),
                          ('loglikelihood', 'Log-likelihood analysis')]),
#     'gsimFormField': {'name': 'gsim', 'label': 'Selected Ground Shaking Intensity Model/s (GSIM):'},
#     'imtFormField': {'name': 'imt', 'label': 'Selected Intensity Measure Type/s (IMT):'}
    }


def index(request):
    '''view for the index page. Defaults to the main view with menu="home"'''
    return render(request, 'index.html', dict(_COMMON_PARAMS, menu='home'))


def main(request, menu):
    '''view for the main page'''
    return render(request, 'index.html', dict(_COMMON_PARAMS, menu=menu))


# @require_http_methods(["GET", "POST"])
def home(request):
    '''view for the home page (iframe in browser)'''
    return render(request, 'home.html', _COMMON_PARAMS)


def trellis(request):
    '''view for the trellis page (iframe in browser)'''
    return render(request, 'trellis.html', dict(_COMMON_PARAMS, form=TrellisForm()))

def test_trellis(request):
    '''view for the trellis (test) page (iframe in browser)'''
    return render(request, 'test_trellis.html', dict(_COMMON_PARAMS, form=TrellisForm()))


def residuals(request):
    '''view for the residuals page (iframe in browser)'''
    return render(request, 'residuals.html', _COMMON_PARAMS)


def loglikelihood(request):
    '''view for the log-likelihood page (iframe in browser)'''
    return render(request, 'loglikelihood.html', _COMMON_PARAMS)


# @api_view(['GET', 'POST'])
def get_init_params(request):  # @UnusedVariable pylint: disable=unused-argument
    """
    Returns input parameters for input selection. Called when app initializes
    """
    # FIXME: Referencing _gsims from BaseForm is quite hacky: it prevents re-calculating
    # the gsims list but there might be better soultions. NOTE: sessions need to much configuration
    # Cahce session are discouraged.:
    # https://docs.djangoproject.com/en/2.0/topics/http/sessions/#using-cached-sessions
    # so for the moment let's keep this hack
    return JsonResponse({'initData': BaseForm._gsims.jsonlist()})


class EgsimQueryView(View):
    '''base view for every EGSIM view handling data request and returning data in response
    this is usually accomplished via a form in the web page or a POST reqeust from
    the a normal query in the standard API'''

    formclass = None

    def get(self, request):
        '''processes a get request'''
        return self.process(dict(request.GET))

    def post(self, request):
        '''processes a post request'''
        return self.process(json.loads(request.body.decode('utf-8')))

    def process(self, params):
        '''processes input params, calls self.process_valid_input if the input is valid
        otherwise returns an appropriate json response with validation error messages'''
        form = self.get_form(params)

        if not form.is_valid():
            jsonerror = self.format_validation_error(form.errors)
            return JsonResponse({'error': jsonerror}, safe=False, status=jsonerror['code'])
        return JsonResponse({'data': self.process_valid_input(form.clean())})

    def get_form(self, params):
        ''' returns the form whereby the validation of input occurs'''
        return self.formclass(data=yaml_load(params))  # pylint: disable=not-callable

    def process_valid_input(self, params):
        ''' core (abstract) method to be implemented in subclasses'''
        raise NotImplementedError()

    @staticmethod
    def format_validation_error(errors):
        '''format the validation error into a google json api format
        https://google.github.io/styleguide/jsoncstyleguide.xml'''
        dic = json.loads(errors.as_json())
        error = {'code': 400, 'message': 'input validation error', 'errors': []}
        for key, values in dic.items():
            for value in values:
                error['errors'].append({'domain': key, 'message': value.get('message', ''),
                                        'reason': value.get('code', '')})
        return error


class TrellisPlots(EgsimQueryView):

    formclass = TrellisForm

    def process_valid_input(self, params):
        return compute_trellis(params)


def get_trellis_plots(request):

    params = json.loads(request.body.decode('utf-8'))  # python 3.5 complains otherwise...
    data = compute_trellis(params)

    if isinstance(data, ErrorDict):
        return JsonResponse(data.as_json(), safe=False, status=400)
    return JsonResponse(data)


def test_err(request):
    raise ValueError('this is a test error!')


def _trellis_response_test():
    dir_ = os.path.abspath(os.path.join(os.path.dirname(__file__),
                                        '..', 'static', 'data', 'test', 'trellis'))
    data = {'names': ['MagnitudeIMTs', 'DistanceIMTs', 'MagnitudeDistanceSpectra'],
            'data': {'sigma': {}, 'mean': {}}}
    for file in os.listdir(dir_):
        absfile = os.path.join(dir_, file)
        if os.path.isfile(absfile):
            name = data['names'][2 if 'spectra' in file else 1 if 'distance' in file else 0]
            data_ = data['data']['sigma'] if 'sigma' in file else data['data']['mean']
            with open(absfile) as opn:
                data_[name] = json.load(opn)
    return data