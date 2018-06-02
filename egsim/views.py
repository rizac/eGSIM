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

from .forms import TrellisForm, BaseForm
from egsim.utils import get_menus, InitData
from django.views.decorators.http import require_http_methods

# FIXME: very hacky to parse the form for defaults, is it there a better choice?
_COMMON_PARAMS = {
    'project_name': 'eGSIM',
    'menus': get_menus(),
    'gsimFormField': {'name': list(BaseForm.declared_fields.keys())[0],
                      'label': list(BaseForm.declared_fields.values())[0].label},
    'imtFormField': {'name': list(BaseForm.declared_fields.keys())[1],
                     'label': list(BaseForm.declared_fields.values())[1].label}
    }

def index(request):
    return render(request, 'index.html', _COMMON_PARAMS)


# @require_http_methods(["GET", "POST"])
def home(request):
    return render(request, 'home.html', _COMMON_PARAMS)


def trellis(request):
    return render(request, 'trellis.html', dict(_COMMON_PARAMS, form=TrellisForm()))


def residuals(request):
    return render(request, 'residuals.html', {'project_name': 'eGSIM',
                                              'form': TrellisForm(),
                                              'menus': get_menus()})


def loglikelihood(request):
    return render(request, 'loglikelihood.html', {'project_name': 'eGSIM',
                                                  'form': TrellisForm(),
                                                  'menus': get_menus()})


# @api_view(['GET', 'POST'])
@csrf_exempt
def get_init_params(request):  # @UnusedVariable pylint: disable=unused-argument
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