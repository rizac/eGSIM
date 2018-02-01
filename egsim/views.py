'''
Created on 17 Jan 2018

@author: riccardo
'''
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
# from rest_framework.decorators import api_view
# from rest_framework.response import Response

from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib.imt import __all__ as available_imts  # FIXME: isn't there a nicer way?

from .forms import RuptureConfigForm
from django.http.response import HttpResponseRedirect
import json
from egsim.forms import InputSelectionForm

def index(request):
    return render(request, 'home.html', {'project_name':'eGSIM', 'form': RuptureConfigForm()})
#     return HttpResponse('Hello World!')

# @api_view(['GET', 'POST'])
@csrf_exempt
def get_init_params(request):
    """
    Returns input parameters for input selection. Called when app initializes
    """
    aval_gsims = [(key,
                  [imt.__name__ for imt in gsim.DEFINED_FOR_INTENSITY_MEASURE_TYPES],
                  gsim.DEFINED_FOR_TECTONIC_REGION_TYPE)
                 for key, gsim in get_available_gsims().items()]
    # print([a[-1] for a in aval_gsims])
    return JsonResponse({'avalGsims': aval_gsims}) 


@csrf_exempt
def calculate_trellisp(request):
    """
    Returns input parameters for input selection. Called when app initializes
    """
    data = json.loads(request.body)
    
    # check first form
    
    # create a form instance and populate it with data from the request:
    form = RuptureConfigForm(data['confRupture'])
    # check whether it's valid:
    if not form.is_valid():
        return HttpResponse(form.errors.as_json(), status = 400, content_type='application/json')

    
    form = InputSelectionForm(data['gsimsInputSel2'])
    # check whether it's valid:
    if not form.is_valid():
        return HttpResponse(form.errors.as_json(), status = 400, content_type='application/json')
    
    return HttpResponse({}, status = 200, content_type='application/json')
    
    # print([a[-1] for a in aval_gsims])
