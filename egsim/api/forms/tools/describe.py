"""Forms description to be used in API tutorials"""

from typing import Type, Union
from collections import defaultdict

from django.forms import (MultipleChoiceField, Field, CharField,
                          ChoiceField, BooleanField, FloatField, IntegerField,
                          ModelChoiceField, ModelMultipleChoiceField)

from .. import EgsimBaseForm
from ..fields import MultipleChoiceWildcardField, NArrayField
from . import field_to_dict, get_choices, get_docstring


def as_dict(form: Union[Type[EgsimBaseForm], EgsimBaseForm]) -> dict:
    """Convert this form to to a JSON serializable dict of information to be
    displayed as parameter help in user requests. Each dict key is a field
    name, mapped to a sub-dict with several field properties

    :param form: EgsimBaseForm class or object (class instance)
    """
    names_of = defaultdict(list)
    for f_name, a_name in form.public_field_names.items():
        names_of[a_name].append(f_name)

    form_data = {}
    for a_name, field in form.declared_fields.items():
        field_dict = field_to_dict(field)
        f_name = names_of[a_name][0]
        opt_names = names_of[a_name][1:]
        # remove unused keys for the help page:
        field_dict['name'] = f_name
        field_dict['opt_names'] = opt_names
        label, help_text = field_dict.pop('label', None), field_dict.pop('help', None)
        desc = get_docstring(label, help_text)
        type_desc = get_field_dtype_description(field)
        field_dict['description'] = f'{desc}{". " if desc else ""}{type_desc}'
        field_dict['is_optional'] = not field.required or field.initial is not None
        form_data[f_name] = field_dict

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


# def is_optional(cls, field):
#     """Return True if the given Field is optional, i.e. if it is not
#     required or its initial value is given (i.e., not None. A field initial
#     value acts as default value when missing)
#
#     :param field: a Field object or a string denoting the name of one of
#         this Form's fields
#     """
#     if isinstance(field, str):
#         field = cls.declared_fields[field]
#     return not field.required or field.initial is not None
