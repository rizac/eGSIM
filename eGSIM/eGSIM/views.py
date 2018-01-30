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
from eGSIM.eGSIM.forms import RuptureConfigForm

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
    return JsonResponse({'avalGsims': aval_gsims}) 