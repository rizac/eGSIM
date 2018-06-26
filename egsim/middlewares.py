'''
Created on 24 Jun 2018

@author: riccardo
'''
import sys

from django.http.response import JsonResponse
from django.utils.deprecation import MiddlewareMixin

class ExceptionHandlerMiddleware(MiddlewareMixin):  # https://stackoverflow.com/a/42233213

    def process_exception(self, request, exception):
        """ Wraps any exception to a JsonResponse with code=500 and an
        (hopefully) meaningful error message"""
        msg, exc = str(exception), exception.__class__.__name__
        code = 500
        return JsonResponse({'error': {'code': code,
                                       'message': ('%s (%s). '
                                                   'Please try again or contact the '
                                                   'software maintainers') % (msg, exc)}},
                            safe=False, status=code)
