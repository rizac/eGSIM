'''
Module handling error responses

Created on 24 Jun 2018

@author: riccardo
'''
import json

from django.http.response import JsonResponse


def invalidform2json(form, code=400,  msg_format='Invalid input in %(names)s'):
    '''Returns a JSON serializable dict from the given invalid form. the dict
    is formatted according to
    https://google.github.io/styleguide/jsoncstyleguide.xml

    :param form: a :class:`django.forms.Form`. `form is_valid()` must have
        been called and must return True
    :param code: HTTP status code, defaults to 400 (client error) when missing
    :param msg_format: the main message of the error. Defaults to
        "Invalid input in %(names)s" when missing. Note that any user-defined
        message can (but it's not mandatory) use the keyword "%(names)s" that
        will be replaced with all invalid form field names (comma separated)
    '''
    errors = errordict2jsonlist(form.errors)
    msg = msg_format % {'names': ', '.join(_['domain'] for _ in errors
                                           if _.get('domain', ''))}
    return exc2json(msg, code=code, errors=errors)


def errordict2jsonlist(errors):
    '''re-formats the given ErrorDict `errors` into a list of dicts.
    Each dict is formatted according to the Google
    format (https://google.github.io/styleguide/jsoncstyleguide.xml):
    ```
        {'domain': <str>, 'message': <str>, 'code': <str>}
    ```
    :param errors: a django :class:`ErrorDict` returned by the `Form.errors`
        property
    '''
    dic = json.loads(errors.as_json())
    errors = []
    for key, values in dic.items():
        for value in values:
            errors.append({'domain': key,
                           'message': value.get('message', ''),
                           'reason': value.get('code', '')})
    return errors


def requestexc2json(exception, code=400, **kwargs):
    '''Converts the given exception or string message `exception` into a json
    response. The difference between this function and `exc2json` is that this
    is more specific and related to any unknown exception in a response.
    As a consequence, the error message is more detailed and prefixed with
    "Unable to perform the request with the current parameters".
    See :func:`exc2json` for details

    :param exception: Exception raised during a request while processing the
        response

    :param kwargs: other optional arguments which will be inserted in the
        response data dict.
    '''
    # sometimes exception is empty or its string representation is empty
    # this is misleading and thus we reformulate the error message:
    errormsg = 'Unable to perform the request with the current parameters'
    if not isinstance(exception, str):
        if str(exception):
            errormsg += " (%s: %s)" % (exception.__class__.__name__,
                                       str(exception))
        else:
            errormsg += " (%s)" % (exception.__class__.__name__)
    else:
        if errormsg:
            errormsg += " (%s)" % str(exception)

    return exc2json(errormsg, code, **kwargs)


def exc2json(exception, code=400, **kwargs):
    '''Converts the given exception or string message `exception` into a json
    response. the response data will be the dict:
    ```
    {
     'error':{
              'message': exception,
              'code': code,
              **kwargs
        }
    }
    ```
    (see https://google.github.io/styleguide/jsoncstyleguide.xml)

    :param exception: Exception or string. If string, it's the exception
    message. Otherwise, the exception message will be built as str(exception)

    :param kwargs: other optional arguments which will be inserted in the
        response data dict.
    '''
    errormsg = str(exception)
    return JsonResponse({'error': dict({'code': code,
                                        'message': errormsg}, **kwargs)},
                        safe=False, status=code)
