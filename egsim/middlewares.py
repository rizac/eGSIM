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
    '''Middleware which captures exceptions and converts them to Json responses'''

#     def process_exception(self, request, exception):
#         """ Wraps any exception to a JsonResponse with code=500 and an
#         (hopefully) meaningful error message"""
#         msg, exc = str(exception), exception.__class__.__name__
#         errormsg = ('%s (%s). Please try again or contact the '
#                     'software maintainers') % (msg, exc)
#         if isinstance(exception, (TemplateDoesNotExist, TemplateSyntaxError)):
#             return render(request, 'base_vue.html', {'server_error_message': errormsg})
# 
#         return self.jsonerr_response(errormsg, code=500)

    @staticmethod
    def jsonerr_response(exception, code=400, **kwargs):
        '''Converts the given exception into a json response. the response data will be the dict:
        ```
        {
         'error':{
                  'message': exception,
                  'code': code,
                  **kwargs
            }
        }
        ```
        For the format used, see https://google.github.io/styleguide/jsoncstyleguide.xml

        :param exception: Exception or string. If string, it's the exception message.
        Otherwise, the exception message will be built from the exception class name <C> and
        the exception string represenation <S> with format '<S> (<C>)'

        :param kwargs: other optional arguments which will be inserted in the response data
        '''
        if isinstance(exception, Exception):
            errormsg = '%s (%s)' % (str(exception), exception.__class__.__name__)
        else:
            errormsg = str(exception)
        return JsonResponse({'error': dict({'code': code, 'message': errormsg}, **kwargs)},
                            safe=False, status=code)
