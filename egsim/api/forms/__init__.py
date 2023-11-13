"""Base eGSIM forms"""

import re
from openquake.hazardlib.gsim.base import GMPE
from openquake.hazardlib.imt import IMT
from typing import Union, Iterable, Any
from datetime import date, datetime
import json
from io import StringIO
from urllib.parse import quote as urlquote

import yaml
from shapely.geometry import Point, shape
from django.core.exceptions import ValidationError
from django.forms import Form, ModelMultipleChoiceField
from django.forms.renderers import BaseRenderer
from django.forms.utils import ErrorDict
from django.forms.forms import DeclarativeFieldsMetaclass  # noqa
from django.forms.fields import Field, ChoiceField, FloatField

from egsim.api import models
from egsim.smtk import validate_inputs, InvalidInput, harmonize_input_gsims, \
    harmonize_input_imts, gsim
from egsim.smtk.validators import IncompatibleInput


class EgsimFormMeta(DeclarativeFieldsMetaclass):
    """EGSIM Form metaclass. Inherits from `DeclarativeFieldsMetaclass` (base metaclass
    for all Django Forms) and sets up the defined field -> API params mappings
    """

    def __new__(mcs, name, bases, attrs):
        new_class = super().__new__(mcs, name, bases, attrs)

        # Set standardized default error messages for each Form field
        _default_error_messages = {
            "required": "This parameter is required",
            "invalid_choice": "Value not found or misspelled: %(value)s",
            "invalid": "Invalid value(s): %(value)s",
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

    # The dict below allows to easily change I/O parameters (keys of `data` in __init__`
    # and `self.errors`) uncoupling them from Field names, which can be kept immutable
    # and thus used reliably as keys of `self.data` and `self.cleaned_data` internally.
    # A Field name can be mapped to several parameters (including the same field name if
    # needed) with the 1st parameter set as primary, and the rest as aliases. Each Field
    # name not found here will be mapped to itself by default. `_field2params` of all
    # superclasses will be merged into this one (see `EgsimFormMeta`). This attr should
    # be private, to access the field and param mapping use `field_iterator()` instead
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
        # store original dict (we assume the values of data are immutable):
        self._input_data = dict(data or {})
        # call super:
        super(EgsimBaseForm, self).__init__(data, files, **kwargs)

        # Fix self.data and add errors in case:
        unknowns = set(self.data) if no_unknown_params else None
        for field_name, field, param_names in self.field_iterator():
            if unknowns is not None:
                unknowns -= set(param_names)
            input_params = tuple(p for p in param_names if p in self.data)
            if len(input_params) > 1:  # names conflict, store error:
                for p in input_params:
                    others = ", ".join(_ for _ in input_params if _ != p)
                    self._add_error(p, ValidationError(f"This parameter conflicts with: "
                                                       f"{others}", code='conflict'))
            elif input_params:
                param_name = input_params[0]
                # Rename the keys of `self.data` (API params) with the mapped field name
                # (see `self.clean` and in subclasses):
                if field_name != param_name:
                    self.data[field_name] = self.data.pop(param_name)
            else:
                # Make missing fields initial value the default, if provided
                # (https://stackoverflow.com/a/20309754):
                if self.fields[field_name].initial is not None:
                    self.data[field_name] = self.fields[field_name].initial

        for unk in unknowns:  # unknown (nonexistent) parameters, store error:
            self._add_error(unk, ValidationError("This parameter does not exist "
                                                 "(check typos)", code='nonexistent'))

    def add_error(self, field: str, error: ValidationError):
        """Call `super.add_error` relaxing some Django restrictions:
         - this method can be safely called at any stage (`super.add_error` raises if
           the form has not been cleaned beforehand, i.e. `self.full_clean` is called)
         - the `field` argument does not need to be a Field name (however, if it does,
           it will be converted to the associated parameter name, if a mapping is found)

        :param field: a Form field name
        :param error: the error as `ValidationError` instance
        """
        # first convert `field` to its mapped parameter name, if any:
        params = self._field2params.get(field, [])
        if params:
            params = [p for p in params if p in self._input_data] or params
        self._add_error(params[0] if params else field, error)

    def _add_error(self, param: str, error: ValidationError):
        """private method performing the same operations as `self.add_error` but storing
        `param` as it is with no conversion or check. Used in `__init__` where we deal
        with input parameters and not Field names

        :param param: a string denoting an input parameter
        :param error: the error as `ValidationError` instance
        """
        # If we did not clean the form yet, `self._errors` is None. So:
        if self._errors is None:
            self._errors = ErrorDict()  # code copied from `super().full_clean`
        # If we do not have the `param` argument in `self._errors`, the `super.add_error`
        # raises. So:
        if param not in self._errors:
            # code copied from `super.add_error`:
            self._errors[param] = self.error_class(renderer=self.renderer)
        # If we did not clean the form yet, `self.cleaned_data` does not exist. So:
        add_attr = not hasattr(self, 'cleaned_data')
        if add_attr:
            setattr(self, 'cleaned_data', {})
        # Now we can safely call the super method:
        super().add_error(param, error)
        # remove cleaned_data if needed:
        if add_attr:
            delattr(self, 'cleaned_data')

    def has_error(self, field, code=None):
        """Call `super.has_error` relaxing some Django conditions: this method can be
        safely called at any stage (`super.has_error` triggers a Form clean if not
        already done, whereas this method simply returns False in case)

        :param field: a Form field name
        :param code: an optional error code (e.g. 'invalid')
        """
        if self._errors:
            # convert field name to mapped params, if any (otherwise map to [itself]):
            for param in self._field2params.get(field, [field]):
                if super().has_error(param, code):
                    return True
        return False

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
        for param_name, errs in errors_dict.items():
            for err in errs:
                errors.append({
                    'location': param_name or 'unspecified',
                    'message': err.get('message', ''),
                    'reason': err.get('code', '')
                })
        if not msg:
            msg = "Invalid request"
            err_param_names = sorted(errors_dict.keys())
            if err_param_names:
                msg += f'. Problems found in: {", ".join(err_param_names)}'
        return {
            'message': msg,
            'errors': errors
        }

    @classmethod
    def field_iterator(cls) -> Iterable[tuple[str, Field, tuple[str, ...]]]:
        """Yield the Fields of this class as tuples of 3 elements:
        ```
        field_name: str, field: Field, params: tuple[str]
        ```
        where field_name and field are the same as returned by
        `cls.declared_fields.items()` and `params` is a tuple of
        API parameter names of the Field (1st param is the default), and it is by
        default a tuple with a single element equal to `field_name`, unless
        different parameter name(s) are provided in `cls._field2params`
        """
        for field_name, field in cls.declared_fields.items():
            params = cls._field2params.get(field_name, (field_name,))
            yield field_name, field, params

    def _get_data(self, compact=True) -> Iterable[tuple[str, Any]]:
        """Yield the Fields of this instance as tuples of 3 elements:
        ```
        param_name: str, param_value: Any, field: Field | None
        ```
        The fields are yielded from the original `data` passed in `__init__`: as such,
        `field` might be None if `param_name` does not match any Form parameter

        @param compact: if True (the default), optional Form parameters (either non
            required or whose value equals the Field initial value) are not yielded
        """
        param2field = {p: f for _, f, ps in self.field_iterator() for p in ps}
        for param_name, value in self._input_data.items():
            field = param2field.get(param_name, None)
            if compact and field is not None:
                field_optional = not field.required or field.initial is not None
                if field_optional and self._input_data[param_name] == field.initial:
                    continue
            yield param_name, value, field

    def as_json(self, compact=True) -> str:
        """Return the `data` argument passed in the constructor in a JSON formatted
        string that can be used in POST requests (if `self.is_valid()` is True)

        @param compact: skip optional parameters (see `compact` in `self._get_data`)
        """
        stream = StringIO()
        json.dump({p: v for p, v, f in self._get_data(compact)},
                  stream, indent=4, separators=(',', ': '), sort_keys=True)
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
        for param_name, value, field in self._get_data(compact):
            docstr = self.get_field_docstring(field) if field else ""
            if docstr:
                stream.write(f'# {docstr}')
                stream.write('\n')
            yaml.dump({param_name: value},
                      stream=stream, Dumper=Dumper, default_flow_style=False)
            stream.write('\n')

        return stream.getvalue()

    @staticmethod
    def get_field_docstring(field: Field, remove_html_tags=False):
        """Return a docstring from the given Form field `label` and `help_text`
        attributes. The returned string will be a one-line (new newlines) string
        FIXME: remove? remove HTML in Fields help_text so that this method is simpler?
        """
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
        for param_name, value, field in self._get_data(compact):
            if isinstance(value, (list, tuple)):
                val = ','.join(f'{urlquote(to_str(v), safe=safe_chars)}' for v in value)
            else:
                val = f'{urlquote(to_str(value), safe=safe_chars)}'
            ret.append(f'{param_name}={val}')
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
        key = 'gsim'
        value = self.cleaned_data.pop(key, None)
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
        key = 'imt'
        value = self.cleaned_data.pop(key, None)
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
        """Run validation where we must validate selected gsim(s) based on
        selected intensity measure type
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


class APIForm(EgsimBaseForm):
    """Basic API Form: handle user request in different media types (json, text)
     and returning the relative response"""

    MIME_TYPE = {
        'csv': "text/csv",
        'json': "application/json",
        'hdf': "application/x-hdf",
        'gzip': "application/gzip"
    }

    @property
    def mime_type(self):
        if not self.is_valid():
            return None
        return self.cleaned_data['format']

    default_format='json'  # change in subclasses if needed

    format = ChoiceField(required=False,
                         label='The format of the returned data (server response)',
                         choices=MIME_TYPE.items())

    @property
    def response_data(self) -> Union[dict, StringIO, None]:
        """Return the response data by processing the form data, or None if
        the form is invalid (`self.is_valid() == False`)
        """
        if not self.is_valid():
            return None
        dformat = self.cleaned_data.get('format', self.__class__.default_format)
        func = getattr(self, f'response_data_{dformat}', None)
        if callable(func):
            return func(self.cleaned_data)
        raise NotImplementedError(f'Format "{dformat}" not implemented')


class GsimFromRegionForm(SHSRForm, APIForm):
    """API Form returning a list of models from a given location and optional
    seismic hazard source regionalizations (SHSR)"""

    def process_data_json(self, cleaned_data: dict) -> list[str]:
        """Process the input data in JSON format
        :param cleaned_data: the result of `self.cleaned_data`
        """
        return sorted(self.get_region_selected_model_names())
