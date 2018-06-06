'''
Created on 17 Jan 2018

@author: riccardo
'''
import os
import json
from collections import OrderedDict

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
# from django.http.response import HttpResponseRedirect
# from django.conf import settings
# from django.views.decorators.http import require_http_methods
# from rest_framework.decorators import api_view
# from rest_framework.response import Response

# from openquake.hazardlib.gsim import get_available_gsims

# import smtk.trellis.trellis_plots as trpl
# import smtk.trellis.configure as rcfg

from egsim.forms import TrellisForm, BaseForm
from egsim.utils import get_menus


# FIXME: very hacky to parse the form for defaults, is it there a better choice?
_COMMON_PARAMS = {
    'project_name': 'eGSIM',
    'menus': OrderedDict([('home', 'Home'), ('trellis', 'Trellis plots'),
                          ('residuals', 'Residuals'),
                          ('loglikelihood', 'Log-likelihood analysis')]),
    'gsimFormField': {'name': 'gsim', 'label': 'Selected Ground Shaking Intensity Model/s (GSIM):'},
    'imtFormField': {'name': 'imt', 'label': 'Selected Intensity Measure Type/s (IMT):'}
    }


def index(request):
    return render(request, 'index.html', _COMMON_PARAMS)


# @require_http_methods(["GET", "POST"])
def home(request):
    return render(request, 'home.html', _COMMON_PARAMS)


def trellis(request):
    return render(request, 'trellis.html', dict(_COMMON_PARAMS, form=TrellisForm()))


def residuals(request):
    return render(request, 'residuals.html', _COMMON_PARAMS)


def loglikelihood(request):
    return render(request, 'loglikelihood.html', _COMMON_PARAMS)


# @api_view(['GET', 'POST'])
@csrf_exempt
def get_init_params(request):  # @UnusedVariable pylint: disable=unused-argument
    """
    Returns input parameters for input selection. Called when app initializes
    """
    # FIXME: Referncing _gsims from BaseForm is quite hacky: it prevents re-calculating the gsims
    # list but there might be better soultions. NOTE: sessions need to much configuration
    # Cahce session are discouraged.:
    # https://docs.djangoproject.com/en/2.0/topics/http/sessions/#using-cached-sessions
    # so for the moment let's keep this hack
    return JsonResponse({'init_data': BaseForm._gsims.jsonlist()})


@csrf_exempt
def validate_trellis_input(request):
    """
    Returns input parameters for input selection. Called when app initializes
    """
    data = json.loads(request.body.decode('utf-8'))  # python 3.5 complains otherwise...

    # create a form instance and populate it with data from the request:
    form = TrellisForm(data)
    # check whether it's valid:
    if not form.is_valid():
        # HttpResponse(form.errors.as_json(), status = 400, content_type='application/json')
        return JsonResponse(form.errors.as_json(), safe=False, status=400)

    return JsonResponse(form.clean())


@csrf_exempt
def get_trellis_plots(request):  # @UnusedVariable pylint: disable=unused-argument
    data = _trellis_response_test()
    return JsonResponse(data)


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