'''
Created on 17 Jan 2018

@author: riccardo
'''
import os
import json

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http.response import HttpResponseRedirect
from django.conf import settings
# from rest_framework.decorators import api_view
# from rest_framework.response import Response

# from openquake.hazardlib.gsim import get_available_gsims
# from openquake.hazardlib.imt import __all__ as available_imts  # FIXME: isn't there a nicer way?

# import smtk.trellis.trellis_plots as trpl
# import smtk.trellis.configure as rcfg

from .forms import RuptureConfigForm, InputSelectionForm
from egsim.utils import get_menus, InitData
from django.views.decorators.http import require_http_methods


def index(request):
    return render(request, 'index.html', {'project_name': 'eGSIM',
                                          'form': RuptureConfigForm(),
                                          'menus': get_menus()})


# @require_http_methods(["GET", "POST"])
def home(request):
    return render(request, 'home.html', {'project_name': 'eGSIM',
                                         'form': RuptureConfigForm(),
                                         'menus': get_menus()})


def trellis(request):
    return render(request, 'trellis.html', {'project_name': 'eGSIM',
                                            'form': RuptureConfigForm(),
                                            'menus': get_menus()})


def residuals(request):
    return render(request, 'residuals.html', {'project_name': 'eGSIM',
                                              'form': RuptureConfigForm(),
                                              'menus': get_menus()})


def loglikelihood(request):
    return render(request, 'loglikelihood.html', {'project_name': 'eGSIM',
                                                  'form': RuptureConfigForm(),
                                                  'menus': get_menus()})


# @api_view(['GET', 'POST'])
@csrf_exempt
def get_init_params(request):  # @UnusedVariable
    """
    Returns input parameters for input selection. Called when app initializes
    """
    init_data = [(key,
                  [imt.__name__ for imt in gsim.DEFINED_FOR_INTENSITY_MEASURE_TYPES],
                  gsim.DEFINED_FOR_TECTONIC_REGION_TYPE,
                  [n for n in gsim.REQUIRES_RUPTURE_PARAMETERS])
                 for key, gsim in InitData.available_gsims.items()]

    return JsonResponse({'init_data': init_data})


@csrf_exempt
def validate_trellis_input(request):
    """
    Returns input parameters for input selection. Called when app initializes
    """
    data = json.loads(request.body.decode('utf-8'))  # python 3.5 complains otherwise...

    # instantiate caption strings:
    rupture_key, inputsel_key = 'confRupture', 'gsimsInputSel'

    # create a form instance and populate it with data from the request:
    form_cr = RuptureConfigForm(data[rupture_key])
    # check whether it's valid:
    if not form_cr.is_valid():
        # HttpResponse(form_cr.errors.as_json(), status = 400, content_type='application/json')
        return JsonResponse(form_cr.errors.as_json(), safe=False, status=400)

    form_is = InputSelectionForm(data[inputsel_key])
    # check whether it's valid:
    if not form_is.is_valid():
        # HttpResponse(form_is.errors.as_json(), status = 400, content_type='application/json')
        return JsonResponse(form_is.errors.as_json(), safe=False, status=400)

    return JsonResponse({rupture_key: form_cr.clean(),
                         inputsel_key: form_is.clean()})


@csrf_exempt
def get_trellis_plots(request):  # @UnusedVariable
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