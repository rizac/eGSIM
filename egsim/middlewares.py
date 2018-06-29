'''
Created on 24 Jun 2018

@author: riccardo
'''
import sys

from django.shortcuts import render
from django.http.response import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.template.exceptions import TemplateDoesNotExist, TemplateSyntaxError

class ExceptionHandlerMiddleware(MiddlewareMixin):  # https://stackoverflow.com/a/42233213

    def process_exception(self, request, exception):
        """ Wraps any exception to a JsonResponse with code=500 and an
        (hopefully) meaningful error message"""
        msg, exc = str(exception), exception.__class__.__name__
        code = 500
        errormsg = ('%s (%s). Please try again or contact the '
                    'software maintainers') % (msg, exc)
        if isinstance(exception, (TemplateDoesNotExist, TemplateSyntaxError)):
            return render(request, 'template_error.html', {'errormsg': errormsg})

        return JsonResponse({'error': {'code': code,
                                       'message': errormsg}},
                            safe=False, status=code)
