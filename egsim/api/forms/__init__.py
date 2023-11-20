"""Base eGSIM forms"""
from __future__ import annotations

from enum import StrEnum

import re
from openquake.hazardlib.gsim.base import GMPE
from openquake.hazardlib.imt import IMT
from typing import Union
from datetime import date, datetime
import json
from io import StringIO
from urllib.parse import quote as urlquote

import yaml
from shapely.geometry import Point, shape
from django.core.exceptions import ValidationError, NON_FIELD_ERRORS
from django.forms import Form, ModelMultipleChoiceField
from django.forms.renderers import BaseRenderer
from django.forms.forms import DeclarativeFieldsMetaclass  # noqa
from django.forms.fields import Field, ChoiceField, FloatField

from egsim.api import models
from egsim.smtk import validate_inputs, InvalidInput, harmonize_input_gsims, \
    harmonize_input_imts, gsim
from egsim.smtk.validators import IncompatibleInput


# parameter error codes:
# invalid_name
# invalid_value
# invalid_choice
# conflicting_names
# missing_value


class EgsimFormMeta(DeclarativeFieldsMetaclass):
    """EGSIM Form metaclass. Inherits from `DeclarativeFieldsMetaclass` (base metaclass
    for all Django Forms) and sets up the defined field -> API params mappings
    """

    def __new__(mcs, name, bases, attrs):
        new_class = super().__new__(mcs, name, bases, attrs)

        # Set standardized default error messages for each Form field
        # FIXME: str-like enum and move it to global var?
        _default_error_messages = {
            "required": "This parameter is required",
            "invalid_choice": "Value not found or misspelled: %(value)s",
            "invalid": "Invalid value: %(value)s",
            # "invalid_list": "Enter a list of values",
        }
        for field in new_class.declared_fields.values():  # same as .base_fields
            field.error_messages |= _default_error_messages
            for err_code, err_msg in field.error_messages.items():
                if err_msg.endswith('.'):  # remove Django msg ending dot, if any:
                    field.error_messages[err_code] = err_msg[:-1]

        # Attribute denoting field -> API params mappings:
        attname = '_field2params'
        # Dict denoting the field -> API params mappings:
        field2params = {}
        # Fill `field2params` with the superclass data. `bases` order is irrelevant
        # because in all `_field2params`s same key / field <=> same value / params:
        for base in bases:
            field2params.update(getattr(base, attname, {}))

        form_fields = set(new_class.declared_fields)
        # Merge this class `field2params` data into `field2params`, and do some check:
        for field, params in attrs.get(attname, {}).items():
            err_msg = f"Error in {name}.{attname}:"
            # no key already implemented in `field2params`:
            if field in field2params:
                raise ValueError(f"{err_msg} '{field}' is already a key of "
                                 f"`{attname}` in some superclass")
            # no key that does not denote a Django Form Field name
            if field not in form_fields:
                raise ValueError(f"{err_msg}: '{field}' must be a Form Field name")
            for param in params:
                # no param equal to another field name:
                if param != field and param in field2params:
                    raise ValueError(f"{err_msg} '{field}' cannot be mapped to the "
                                     f"Field name '{param}'")
                # no param keyed by multiple field names:
                dupes = [f for f, p in field2params.items() if param in p]
                if dupes:
                    raise ValueError(f"{err_msg} '{field}' cannot be mapped to "
                                     f"'{param}', as the latter is already keyed by "
                                     f"{', '.join(dupes)}")
            # all values must be list or tuples:
            if isinstance(params, list):
                params = tuple(params)
            elif not isinstance(params, tuple):
                raise ValueError(f"{err_msg} dict values must be lists or tuples")
            # all good. Merge into `field2params`:
            field2params[field] = params

        # assign new dict of public field name:
        setattr(new_class, attname, field2params)
        return new_class


_base_singleton_renderer = BaseRenderer()  # singleton no-op renderer, see below


def get_base_singleton_renderer(*a, **kw) -> BaseRenderer:
    """Return a singleton, no-op "dummy" renderer instance (we use Django as REST API
    only with HTML rendering delegated to SPA in JavaScript).
    Because this function is set as "FORM_RENDERER" in the settings file, it will be
    called by `django forms.renderers.get_default_renderer` every
    time a default renderer is needed (See e.g. `django.forms.forms.Form` and `ErrorDict`
    or `ErrorList` - both in the module `django.forms.utils`)
    """
    return _base_singleton_renderer


class EgsimBaseForm(Form, metaclass=EgsimFormMeta):
    """Base eGSIM form"""

    # make code linters happy (attr created in Django DeclarativeFieldsMetaclass):
    base_fields: dict[str, Field]

    # The dict below allows to easily change Field names without breaking the code.
    # Just map any Field name implemented on this class to several parameters
    # (including the same field name if needed), where the 1st parameter will be
    # considered the primary name, and the rest aliases (if a Field name is mapped only
    # to itself, it can be omitted).
    # Notes: this attribute is merged with superclasses implementations (see
    # `EgsimFormMeta`) and should be private, use `param_names_of` or `param_name_of`
    # instead. Being immutable, Field names (accessible via `class.base_fields`) should
    # be used internally during form validation, e.g. as keys of `self.data` and
    # `self.cleaned_data`. I/O parameters are the field names exposed publicly,
    # e.g. as input (`data` passed in `__init__`) or output (`self.errors_json_dict`).
    _field2params: dict[str, list[str]]

    def __init__(self, data=None, files=None, no_unknown_params=True, **kwargs):
        """Override init: re-arrange `self.data` (renaming each key with the
        corresponding field name, if needed) and treating non None initial values
        as default values for missing fields. As such, `data` might be modified inplace.

        :param data: the Form data (dict or None)
        :param files: the Form files
        :param no_unknown_params: boolean indicating whether unknown parameters (`data`
            keys) should invalidate the Form. The default is True to prevent misspelled
            parameters to be treated as missing and thus potentially assigned a default
            "wrong" value with no warnings
        """
        # remove colon in labels by default in templates:
        kwargs.setdefault('label_suffix', '')
        # Form Field names mapped to the relative param given as input:
        self._field2inputparam = {}
        # call super:
        super(EgsimBaseForm, self).__init__(data, files, **kwargs)

        # Fix self.data and add errors in case:
        unknowns = set(self.data if no_unknown_params else [])
        errors = []
        for field_name, field in self.base_fields.items():
            param_names = self.param_names_of(field_name)
            unknowns -= set(param_names)
            input_param_names = tuple(p for p in param_names if p in self.data)
            if len(input_param_names) > 1:  # names conflict, store error:
                names = " and ".join(input_param_names)
                errors.append(ValidationError(f'{names}: names conflict',
                                              code=f'names_conflict'))
                # keep only the first param in `self.data`
                for p in input_param_names[1:]:
                    self.data.pop(p)
                # now let's fall in the next if below:
                input_param_names = input_param_names[:1]
            if len(input_param_names) == 1:
                input_param_name = input_param_names[0]
                self._field2inputparam[field_name] = input_param_name
                # Rename the keys of `self.data` (API params) with the mapped
                # field name (see `self.clean` and in subclasses):
                if field_name != input_param_name:
                    self.data[field_name] = self.data.pop(input_param_name)
            else:
                # Make missing fields initial value the default, if provided
                # (https://stackoverflow.com/a/20309754):
                if self.fields[field_name].initial is not None:
                    self.data[field_name] = self.fields[field_name].initial

        for unk in unknowns:
            errors.append(ValidationError(f'Invalid name(s): {unk}',
                                          code=f'invalid_name'))
        if errors:
            # Add errors. Notes: `add_error(N, ...)` works only if N is None or
            # an existing field name, and will force a form full clean (so that we
            # might end up adding more errors than those added below)
            self.add_error(None, errors)

    def has_error(self, field, code=None):
        """Call `super.has_error` without forcing a full clean (if the form has not
        been cleaned, return False)

        :param field: a Form field name (not an input parameter name)
        :param code: an optional error code (e.g. 'invalid')
        """
        return super().has_error(field, code) if self._errors else False

    def errors_json_data(self, msg: str = None) -> dict:
        """Reformat `self.errors.get_json_data()` and return a JSON serializable dict
        with keys `message` (the `msg` argument or - if missing - a global error message
        summarizing all errors), and `errors`, a list of `dict[str, str]` elements, where
        each dict represents a parameter and has keys "location" (the parameter name),
        "message" (the detailed error message related to the parameter), and "reason" (an
        error code indicating the type of error, e.g. "required", "invalid")

        NOTE: This method triggers a full Form clean (`self.full_clean`). It should
        be usually called if `self.is_valid()` returns False

        For details see:
        https://cloud.google.com/storage/docs/json_api/v1/status-codes
        https://google.github.io/styleguide/jsoncstyleguide.xml
        """
        errors_dict: dict[str, list[dict[str, str]]] = self.errors.get_json_data()
        if not errors_dict:
            return {}

        errors = []
        # build errors dict:
        for field_name, errs in errors_dict.items():
            param_name = ''
            if field_name != NON_FIELD_ERRORS:
                # if we called add_error(None, ...) then field_name is NON_FIELD_ERRORS
                param_name = self.param_name_of(field_name)
            for err in errs:
                errors.append({
                    'location': param_name,
                    'message': err.get('message', ''),
                    'reason': err.get('code', '')
                })
        if not msg:
            msg = "Invalid request"
            err_param_names = sorted({self.param_name_of(f) for f in errors_dict
                                      if f != NON_FIELD_ERRORS})
            if err_param_names:
                msg += f'. Problems found in: {", ".join(err_param_names)}'
        return {
            'message': msg,
            'errors': errors
        }

    def param_name_of(self, field: str) -> str:
        """Return the input parameter name of `field`. If no parameter name mapped to
        `field` has been provided as input `data`, return the first parameter name
        of `field` or, in case of no mapping, `field` itself
        """
        if field in self._field2inputparam:  # param is given in this form `data`:
            return self._field2inputparam[field]
        return self.param_names_of(field)[0]  # class-level method

    @classmethod
    def param_names_of(cls, field: str) -> tuple[str]:
        """Return the parameter names of `field` registered at a class-level. The
        returned tuple has nonzero length and might contain the passed field argument.
        In case of length > 1, the first item is the primary parameter name
        """
        return cls._field2params.get(field, (field,))

    def as_json(self, compact=True) -> str:
        """Return the `data` argument passed in the constructor in a JSON formatted
        string that can be used in POST requests (if `self.is_valid()` is True)

        @param compact: skip optional parameters (see `compact` in `self._get_data`)
        """
        stream = StringIO()
        ret = {}
        for field, value in self.data.items():
            if compact and \
                    self._is_default_value_for_field(field, value):  # class level attr
                continue
            ret[self.param_name_of(field)] = value
        json.dump(ret, stream, indent=2, separators=(',', ': '), sort_keys=True)
        return stream.getvalue()

    def as_yaml(self, compact=True) -> str:
        """Return the `data` argument passed in the constructor as YAML formatted
        string (with parameters docstrings when available) that can be used in POST
        requests (if `self.is_valid()` is True)

        @param compact: skip optional parameters (see `compact` in `self._get_data`)
        """
        class Dumper(yaml.SafeDumper):
            """Force indentation of lists ( https://stackoverflow.com/a/39681672)"""

            def increase_indent(self, flow=False, indentless=False):
                return super(Dumper, self).increase_indent(flow, False)

        stream = StringIO()
        for field, value in self.data.items():
            if compact and \
                    self._is_default_value_for_field(field, value):  # class level attr
                continue
            docstr = self.get_field_docstring(field)
            if docstr:
                stream.write(f'# {docstr}')
                stream.write('\n')
            yaml.dump({self.param_name_of(field): value},
                      stream=stream, Dumper=Dumper, default_flow_style=False)
            stream.write('\n')

        return stream.getvalue()

    @classmethod
    def _is_default_value_for_field(cls, field: Union[str, Field], value):
        """Return True if the given value is the default value for the given
        field and can be omitted in `self.data`"""
        if isinstance(field, str):
            field = cls.declared_fields.get(field, None)
        if field:
            field_optional = not field.required or field.initial is not None
            if field_optional and value == field.initial:
                return True
        return False

    @classmethod
    def get_field_docstring(cls, field: Union[str, Field], remove_html_tags=False):
        """Return a docstring from the given Form field `label` and `help_text`
        attributes. The returned string will be a one-line (new newlines) string
        FIXME: remove? remove HTML in Fields help_text so that this method is simpler?
        """
        if isinstance(field, str):
            field = cls.declared_fields.get(field, None)
        if not field:
            return ""
        field_label = getattr(field, 'label')
        field_help_text = getattr(field, 'help_text')
        label = (field_label or '') + \
                ('' if not field_help_text else f' ({field_help_text})')
        if label and remove_html_tags:
            # replace html tags, e.g.: "<a href='#'>X</a>" -> "X",
            # "V<sub>s30</sub>" -> "Vs30"
            _html_tags_re = re.compile('<(\\w+)(?: [^>]+|)>(.*?)</\\1>')
            # replace html characters with their content
            # (or empty str if no content):
            label = _html_tags_re.sub(r'\2', label)
        # replace newlines for safety:
        label = label.replace('\r\n', ' ').replace('\n', ' ').replace('\r', ' ')
        return label

    QUERY_STRING_SAFE_CHARS = "-_.~!*'()"

    def as_querystring(self, compact=True) -> str:
        """Return the `data` argument passed in the constructor as query string
        that can be used in GET requests (if `self.is_valid()` is True)

        @param compact: skip optional parameters (see `compact` in `self._get_data`)
        """
        # Letters, digits, and the characters '_.-~' are never quoted. These are
        # the additional safe characters (we include the former for safety):
        safe_chars = self.QUERY_STRING_SAFE_CHARS
        ret = []
        to_str = self.obj_as_querystr
        for field, value in self.data.items():
            if compact and \
                    self._is_default_value_for_field(field, value):  # class level attr
                continue
            if isinstance(value, (list, tuple)):
                val = ','.join(f'{urlquote(to_str(v), safe=safe_chars)}' for v in value)
            else:
                val = f'{urlquote(to_str(value), safe=safe_chars)}'
            ret.append(f'{self.param_name_of(field)}={val}')
        return '&'.join(ret)

    @staticmethod
    def obj_as_querystr(obj: Union[bool, None, str, date, datetime, int, float]) -> str:
        """Return a string representation of `obj` for injection into URL query
        strings. No character of the returned string is escaped (see
        :func:`urllib.parse.quote` for that)

        @return "null" if obj is None, "true/false"  if `obj` is `bool`,
            `obj.isoformat()` if `obj` is `date` or `datetime`, `str(obj)` in any other
             case
        """
        if obj is None:
            return "null"
        if obj is True or obj is False:
            return str(obj).lower()
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return str(obj)


class SHSRForm(EgsimBaseForm):
    """Base class for all Form accepting a list of models in form of location
    (lat lon) and optional list of seismic hazard source regionalizations (SHSR)"""

    # Custom API param names (see doc of `EgsimBaseForm._field2params` for details):
    _field2params = {
        'latitude': ['latitude', 'lat'],
        'longitude': ['longitude', 'lon'],
        'regionalization': ['regionalization', 'shsr']
    }

    latitude = FloatField(label='Latitude', min_value=-90., max_value=90.,
                          required=False)
    longitude = FloatField(label='Longitude', min_value=-180., max_value=180.,
                           required=False)
    regionalization = ModelMultipleChoiceField(
        queryset=models.Regionalization.objects.only('name', 'media_root_path').
            filter(hidden=False),
        initial=models.Regionalization.objects.only('name', 'media_root_path').
            filter(hidden=False),
        to_field_name="name",
        label='Regionalization',
        required=False)

    def get_region_selected_model_names(self) -> set[str]:
        gsims = set()
        cleaned_data = self.cleaned_data
        lon = cleaned_data.get('longitude', None)
        lat = cleaned_data.get('latitude', None)
        if lat is None or lon is None:
            return gsims
        point = Point(lon, lat)
        for obj in cleaned_data['regionalization']:
            with open(obj.filepath, 'r') as _:
                features = json.load(_)['features']
            for feat in features:
                geometry, models = feat['geometry'], feat['properties']['models']
                # if we already have all models, skip check:
                if set(models) - gsims:
                    if shape(geometry).contains(point):
                        gsims.update(models)
        return gsims


class GsimImtForm(SHSRForm):
    """Base abstract-like form for any form requiring Gsim+Imt selection"""

    # Custom API param names (see doc of `EgsimBaseForm._field2params` for details):
    _field2params: dict[str, list[str]] = {'gsim': ['model', 'gsim', 'gmm']}

    # Set simple Fields and perform validation in `clean_gsim` and `clean_imt`:
    gsim = Field(required=False, label="Model(s)",
                 widget=ModelMultipleChoiceField.widget)
    imt = Field(required=False, label='Intensity Measure Type(s)',
                widget=ModelMultipleChoiceField.widget)

    accept_empty_gsim_list = False  # override in subclasses if needed
    accept_empty_imt_list = False  # see above (for imts)

    def clean_gsim(self) -> dict[str, GMPE]:
        """Custom gsim clean.
        The return value will replace self.cleaned_data['gsim']
        """
        key = 'gsim'
        value = self.cleaned_data.get(key, None)
        if not value:
            if not self.accept_empty_gsim_list:
                raise ValidationError(
                    self.fields[key].error_messages['required'],
                    code='required')
            return {}
        if type(value) not in (list, tuple):
            value = [value]
        try:
            ret = harmonize_input_gsims(value)
            for name in self.get_region_selected_model_names():
                if name not in ret:
                    ret[name] = gsim(name)
            return ret
        except InvalidInput as err:
            # FIXME handle error messages and also in clean_imt below:
            raise ValidationError(
                self.fields[key].error_messages["invalid_choice"],
                code="invalid_choice",
                params={"value": str(err)},
            )

    def clean_imt(self) -> dict[str, IMT]:
        """Custom gsim clean.
        The return value will replace self.cleaned_data['imt']
        """
        key = 'imt'
        value = self.cleaned_data.get(key, None)
        if not value:
            if not self.accept_empty_imt_list:
                raise ValidationError(
                    self.fields[key].error_messages['required'],
                    code='required')
            return {}
        if type(value) not in (list, tuple):
            value = [value]
        try:
            return harmonize_input_imts(value)
        except InvalidInput as err:
            raise ValidationError(
                self.fields[key].error_messages["invalid_choice"],
                code="invalid_choice",
                params={"value": str(err)},
            )

    def clean(self):
        """Perform a final validation checking models and intensity measures
        compatibility
        """
        gsim, imt = 'gsim', 'imt'
        cleaned_data = super().clean()

        # if any of the if above was true, then the parameter has been removed from
        # cleaned_data. If both are provided, check gsims and imts match:
        if not self.has_error(gsim) and not self.has_error(imt):
            try:
                validate_inputs(cleaned_data[gsim], cleaned_data[imt])
            except IncompatibleInput as err:
                # add error to form:
                invalid_gsims = [i[0] for i in err.args]
                invalid_imts = set(i for v in err.args for i in v[1:])
                code = 'invalid_model_imt_combination'
                err_gsim = ValidationError(f"{len(invalid_gsims)} model(s) not defined "
                                           "for all supplied imt(s)", code=code)
                err_imt = ValidationError(f"{len(invalid_imts)} imt(s) not defined for "
                                          "all supplied model(s)", code=code)
                # add_error removes also the field from self.cleaned_data:
                self.add_error(gsim, err_gsim)
                self.add_error(imt, err_imt)

        return cleaned_data


class MIMETYPE(StrEnum):  # noqa
    """An enum of supported mime types (content_type in Django Response) loosely
    copied from mimetypes.types_map (https://docs.python.org/3.8/library/mimetypes.html)
    """
    CSV = "text/csv"
    JSON = "application/json"
    HDF = "application/x-hdf"
    PNG = 'image/png'
    PDF = 'application/pdf'
    SVG = 'image/svg+xml'
    # GZIP = "application/gzip"


class APIForm(EgsimBaseForm):
    """API Form is the Base Form for the eGSIM API request/response. It implements:
    1. a "format" Field/parameter to validate a request format (defaulting to "json")
        and return the relative content type (mime type) in the cleaned data
    2. An abstract-like `response_json` method and, for any other supported format
        the relative `response_data_<format>` method (usually converting from or to
        the JSON response data)
    """

    format = ChoiceField(required=False,
                         initial=MIMETYPE.JSON.name.lower(),
                         label='The format of the data returned by the web service',
                         choices=[(m.name.lower(), m) for m in MIMETYPES])  # noqa

    def clean_format(self) -> str:
        """Custom format clean.
        The return value will replace self.cleaned_data['format']
        """
        return MIMETYPE[self.cleaned_data.get('format', "").upper()]

    def response_data_json(self, cleaned_data:dict) -> dict:
        """Return the response data from this Form `cleaned_data` as a JSON-serializable
        `dict`. Subclasses supporting different formats other than the default ('json')
        should implement the relative `response_<format>` methods (any lowercase name
        of the `MIMETYPE` enum, e.g. `response_csv(cleaned_data)`)
        """
        raise NotImplementedError()


class GsimFromRegionForm(SHSRForm, APIForm):
    """API Form returning a list of models from a given location and optional
    seismic hazard source regionalizations (SHSR)"""

    def response_data_json(self, cleaned_data:dict) -> dict:
        """Return the API response from the Form cleaned_data"""
        return {'models': sorted(self.get_region_selected_model_names())}
