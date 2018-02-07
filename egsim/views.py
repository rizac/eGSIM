'''
Created on 17 Jan 2018

@author: riccardo
'''
import json

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.http.response import HttpResponseRedirect
# from rest_framework.decorators import api_view
# from rest_framework.response import Response

from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib.imt import __all__ as available_imts  # FIXME: isn't there a nicer way?

# import smtk.trellis.trellis_plots as trpl
# import smtk.trellis.configure as rcfg

from .forms import RuptureConfigForm, InputSelectionForm

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
def validate_trellis_input(request):
    """
    Returns input parameters for input selection. Called when app initializes
    """
    data = json.loads(request.body)
    
    # instantiate caption strings:
    CR, IS = 'confRupture', 'gsimsInputSel'
    
    # create a form instance and populate it with data from the request:
    form_cr = RuptureConfigForm(data[CR])
    # check whether it's valid:
    if not form_cr.is_valid():
        return HttpResponse(form_cr.errors.as_json(), status = 400, content_type='application/json')

    form_is = InputSelectionForm(data[IS])
    # check whether it's valid:
    if not form_is.is_valid():
        return HttpResponse(form_is.errors.as_json(), status = 400, content_type='application/json')
    

    return HttpResponse({CR: form_cr.clean(),
                         IS: form_is.clean()}, status = 200, content_type='application/json')
    
    # print([a[-1] for a in aval_gsims])
