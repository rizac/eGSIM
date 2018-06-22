from yaml import safe_load, YAMLError
import os
from io import StringIO
from django.core.exceptions import ValidationError


def validate(formclass):
    '''creates a validator for a function processing a dict resulting e,g, from a web request
    The validator must be a django form that will be called with the dict. The validated
    dict will then be passed to the decorated function. The dict must be the function's first
    argumeent.

    wraps the decorated function and returns the tuple
    (form, output)

    where output is the output of the decorated function, ior None if the form is not valid

    Example:

    @validate(MyForm)
    def process_params(params, *args, **kwargs):
        # here params is assured to be validated with 'MyForm' and can be safely processed
    '''
    def real_decorator(function):
        def wrapper(params, *args, **kwargs):
            form = formclass(data=yaml_load(params))
            return (form, None) if not form.is_valid() else \
                (form, function(dict(form.clean()), *args, **kwargs))
        return wrapper
    return real_decorator


def yaml_load(obj):
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, str):
        if os.path.isfile(obj):
            stream = open(obj, 'r')
        else:
            stream = StringIO(obj)
    elif not hasattr(obj, 'read') or not hasattr(obj, 'close'):
        raise TypeError('Invalid input, expected data in YAML syntax (POST request) '
                        'or path pointing to an existing YAML file on server, '
                        'found %s' % str(obj.__class__.__name__))
    else:
        stream = obj

    try:
        ret = safe_load(stream)
        # for some weird reason, in case of a string ret is the string itself, and no error
        # is raised. Let's do it here:
        if not isinstance(ret, dict):
            raise YAMLError('Invalid input %s: parsed output is %s, expected %s'
                            % (str(obj), ret.__class__.__name__, {}.__class__.__name__))
        return ret
    except YAMLError as exc:
        raise YAMLError('malformed YAML syntax in input data: %s' % str(exc)) from None
    finally:
        stream.close()
