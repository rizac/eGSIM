'''
Created on 17 Jan 2018

@author: riccardo
'''
import os
import json
from collections import OrderedDict

from yaml.error import YAMLError

from django.http import JsonResponse
from django.shortcuts import render
# from django.views.decorators.csrf import csrf_exempt
from django.views.generic.base import View

from egsim.middlewares import ExceptionHandlerMiddleware
from egsim.forms import TrellisForm, BaseForm
from egsim.core.trellis import compute_trellis
from egsim.core.utils import EGSIM
from egsim.core.shapes import load_share


_COMMON_PARAMS = {
    'project_name': 'eGSIM',
    'debug': True,
    'menus': OrderedDict([('home', 'Home'), ('trsel', 'Tectonic region Selection'),
                          ('trellis', 'Trellis plots'),
                          ('residuals', 'Residuals'),
                          ('loglikelihood', 'Log-likelihood analysis')]),
    }


def index(request):
    '''view for the index page. Defaults to the main view with menu="home"'''
    return render(request, 'index.html', dict(_COMMON_PARAMS, menu='home'))


def main(request, menu):
    '''view for the main page'''
    return render(request, 'index.html', dict(_COMMON_PARAMS, menu=menu))


def home(request):
    '''view for the home page (iframe in browser)'''
    return render(request, 'home.html', _COMMON_PARAMS)


def trsel(request):
    '''view for the trellis page (iframe in browser)'''
    return render(request, 'trsel.html', dict(_COMMON_PARAMS, form=BaseForm(),
                                              trprojects={'SHARE': load_share()},
                                              selproject='SHARE'))


def trellis(request):
    '''view for the trellis page (iframe in browser)'''
    return render(request, 'trellis.html', dict(_COMMON_PARAMS, form=TrellisForm()))


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
    return JsonResponse({'initData': EGSIM.jsonlist()})


class EgsimQueryView(View):
    '''base view for every eGSIM view handling data request and returning data in response
    this is usually accomplished via a form in the web page or a POST reqeust from
    the a normal query in the standard API'''

    formclass = None
    EXCEPTION_CODE = 400
    VALIDATION_ERR_MSG = 'input validation error'

    def get(self, request):
        '''processes a get request'''
        return self.response(dict(request.GET))

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
            return ExceptionHandlerMiddleware.jsonerr_response(cls.VALIDATION_ERR_MSG,
                                                               code=cls.EXCEPTION_CODE,
                                                               errors=errors)

        return JsonResponse(cls.process(form.clean()))

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


class TrellisPlotsView(EgsimQueryView):
    '''EgsimQueryView subclass for generating Trelli plots responses'''

    formclass = TrellisForm

    @classmethod
    def process(cls, params):
        return compute_trellis(params)


# TESTS (FIXME: REMOVE?)

def test_err(request):
    raise ValueError('this is a test error!')


def trellis_test(request):
    '''view for the trellis (test) page (iframe in browser)'''
    return render(request, 'trellis_test.html', dict(_COMMON_PARAMS, form=TrellisForm()))
