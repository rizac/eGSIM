'''
Core functionalities acting as interface between openquake / smtk and the web
API
'''
import os
from io import StringIO
from yaml import safe_load, YAMLError
from django.core.exceptions import ValidationError
from django.http.response import JsonResponse


def yaml_load(obj):
    '''Safely loads the YAML-formatted object `obj` into a dict.

    :param obj: (dict, stream, string denoting an existing file path, or string denoting
        the file content in YAML syntax): If stream (i.e., an object with the `read` attribute),
        uses it for reading and parsing its content into dict. If dict, this method is no-op
        and the dict is returned, if string denoting an existing file, a stream is opened
        from the file and processed as explained above (the stream will be closed in this case).
        If string, the string is treated as YAML content and parsed: in this case, the output
        must be a dict otherwise a YAMLError is thrown

    :raises: YAMLError
    '''
    if isinstance(obj, dict):
        return obj

    close_stream = False
    if isinstance(obj, str):
        close_stream = True
        if os.path.isfile(obj):  # file input
            stream = open(obj, 'r')
        else:
            stream = StringIO(obj)  # YAML content input
    elif not hasattr(obj, 'read'):
        # raise a general message meaningful for a Rest framework and a web app:
        raise YAMLError('Invalid input, expected POST data as string in YAML syntax, '
                        'found %s' % str(obj.__class__.__name__))
    else:
        stream = obj

    try:
        ret = safe_load(stream)
        # for some weird reason, in case of a string ret is the string itself, and no error
        # is raised. Let's do it here:
        if not isinstance(ret, dict):
            raise YAMLError('Malformed input: parsed output is %s, expected %s'
                            % (ret.__class__.__name__, {}.__class__.__name__))
        return ret
    except YAMLError as exc:
        raise YAMLError('Malformed input (syntax error): %s' % str(exc)) from None
    finally:
        if close_stream:
            stream.close()
