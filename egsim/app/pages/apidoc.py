"""Forms description to be used in API tutorials"""

from typing import Type, Union
from collections import defaultdict

from django.forms import (MultipleChoiceField, Field, CharField,
                          ChoiceField, BooleanField, FloatField, IntegerField,
                          ModelChoiceField, ModelMultipleChoiceField)

from .egsim import field_to_dict, get_choices
from .. import TAB
from ...api.models import FlatfileColumn
from ...api.views import QUERY_PARAMS_SAFE_CHARS
from ...api.forms import EgsimBaseForm
from ...api.forms.fields import (MultipleChoiceWildcardField, NArrayField,
                                 get_field_docstring)


def get_context(debug: bool) -> dict:
    """The context to be injected in the template of the api doc HTML page"""
    # baseurl is the base URL for the services explained in the tutorial
    # It is the request.META['HTTP_HOST'] key. But during testing, this
    # key is not present. Actually, just use a string for the moment:
    baseurl = "<eGSIMsite>"
    # Note that the keus of the egsim_data dict below should NOT
    # be changed: if you do, you should also change the templates
    egsim_data = {
        'trellis': {
            'title': TAB.trellis.title,
            'path': " or ".join(TAB.trellis.urls),
            'form': as_dict(TAB.trellis.formclass),
            'key': TAB.trellis.name
        },
        'residuals': {
            'title': TAB.residuals.title,
            'path': " or ".join(TAB.residuals.urls),
            'form': as_dict(TAB.residuals.formclass),
            'key': TAB.residuals.name
        },
        'testing': {
            'title': TAB.testing.title,
            'path': " or ".join(TAB.testing.urls),
            'form': as_dict(TAB.testing.formclass),
            'key': TAB.testing.name
        }
    }
    return {
        'debug': debug,
        'query_params_safe_chars': QUERY_PARAMS_SAFE_CHARS,
        'egsim_data': egsim_data,
        'baseurl': baseurl,
        'gmt':_get_flatfile_column_desc()
    }


def as_dict(form: Union[Type[EgsimBaseForm], EgsimBaseForm]) -> dict:
    """Convert the given form to to a JSON serializable dict of information to be
    displayed as parameter help in user requests. Each dict key is a field
    name, mapped to a sub-dict with several field properties

    :param form: EgsimBaseForm class or object (class instance)
    """
    form_data = {}
    for param_names, field_name, field in form.params():
        field_dict = field_to_dict(field)
        field_dict['name'] = param_names[0]
        field_dict['opt_names'] = param_names[1:]
        desc = get_field_docstring(field)
        type_desc = get_field_dtype_description(field)
        field_dict['description'] = f'{desc}{". " if desc else ""}{type_desc}'
        field_dict['is_optional'] = not field.required or field.initial is not None
        form_data[param_names[0]] = field_dict

    return form_data


def get_field_dtype_description(field: Field) -> str:
    """Return the Field data type description as human readable string

    :param field: a Django Field (including EGSIm specific fields in
        `api.forms.fields`)
    """
    # call get_field_dtype but consider egsim specific fields:
    if isinstance(field, NArrayField):
        if field.min_count is not None and field.min_count > 1:
            dtype = list[float]
        else:
            dtype = Union[float, list[float]]
    else:
        dtype = get_field_dtype(field)
        if isinstance(field, MultipleChoiceWildcardField):
            # convert list[T] into Union[T, list[T]] (T = int, float, str, bool)
            dtype = Union[dtype.__args__[0], dtype]  # noqa

    try:
        type_desc = SUPPORTED_FIELDS_DTYPES[dtype]
    except KeyError:
        raise ValueError(f'Unsupported Type {dtype}')

    min_val, max_val = getattr(field, 'min_val', None), getattr(field, 'max_val', None)
    if min_val is not None and max_val is None:
        type_desc += f'. Values must be ≥ {min_val}'
    elif min_val is None and max_val is not None:
        type_desc += f'. Values must be ≤ {max_val}'
    elif min_val is not None and max_val is not None:
        type_desc += f'. Values must be in [{min_val}, {max_val}]'

    return type_desc


# supported Python data types:
SUPPORTED_FIELDS_DTYPES = {
    str: 'String',
    list[str]: 'List of strings',
    Union[str, list[str]]: 'String or list of strings',
    int: 'Number',
    list[int]: 'List of numbers',
    Union[int, list[int]]: 'Number or list of numbers',
    float: 'Number',
    list[float]: 'List of numbers',
    Union[float, list[float]]: 'Number or list of numbers',
    bool: 'Boolean (true or false)',
    list[bool]: 'List of booleans (true or false)',
    Union[bool, list[bool]]: 'Boolean (true or false) or list of booleans',
}


def get_field_dtype(field: Field) -> Type:
    """Return the Python data type corresponding to the given Django field.
    See SUPPORTED_FIELDS_DTYPES keys for a collection of data types that can
    be returned

    :param field: a Django form Field
    :return: the Python type, e.g. str, list[str], float
    """
    if isinstance(field, CharField):
        return str
    elif isinstance(field, (ChoiceField, MultipleChoiceField, ModelChoiceField,
                            ModelMultipleChoiceField)):
        # (isinstance(ChoiceField) should be sufficient, but let's be explicit)
        _types = set(type(_[0]) for _ in get_choices(field))
        if len(_types) != 1:
            raise ValueError(f'Field choices must be all of the same '
                             f'Python type, found: {_types}')
        field_dtype = next(iter(_types))
        if isinstance(field, (MultipleChoiceWildcardField,
                              ModelMultipleChoiceField)):
            return list[field_dtype]
        return field_dtype
    elif isinstance(field, BooleanField):
        return bool
    elif isinstance(field, (IntegerField, FloatField)):
        # (isinstance(IntegerField) should be sufficient, but let's be explicit)
        return float if isinstance(field, FloatField) else int
    else:
        raise ValueError(f'No data type specified for Field {field}')


def _get_flatfile_column_desc(as_html=True):
    ret = {}
    for ff_field in FlatfileColumn.objects.all():
        name = ff_field.name
        props = ff_field.properties
        dtype = props['dtype']
        if isinstance(dtype, (list, tuple)):
            type2str = 'categorical. Possible values:\n' + \
                       "\n".join(str(_) for _ in dtype)
        else:
            type2str = str(dtype)
        default = str(props.get('default', ''))
        if as_html:
            type2str = "<span style='white-space: nowrap'>%s</span>" % \
                type2str.replace('\n', '<br>')
        ret[name] = (type2str, default)
    return ret


