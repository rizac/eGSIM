"""Base eGSIM forms"""

import re
from django.forms.renderers import BaseRenderer
from django.forms.utils import ErrorDict
from typing import Union, Iterable, Any
from datetime import date, datetime
import json
import yaml
from itertools import chain, repeat
from io import StringIO
import csv
from urllib.parse import quote as urlquote

from shapely.geometry import Polygon, Point
from django.core.exceptions import ValidationError
from django.forms.forms import DeclarativeFieldsMetaclass  # noqa
from django.forms import Form

from .fields import (MultipleChoiceWildcardField, ImtField, ChoiceField, Field,
                     FloatField, get_field_docstring, NArrayField,
                     _default_error_messages)
from .. import models


class EgsimFormMeta(DeclarativeFieldsMetaclass):
    """EGSIM Form metaclass. Inherits from `DeclarativeFieldsMetaclass` (base metaclass
    for all Django Forms) and sets up the defined field -> API params mappings
    """

    def __new__(mcs, name, bases, attrs):
        new_class = super().__new__(mcs, name, bases, attrs)

        # Adjust Fields error messages with our defaults:
        if _default_error_messages:
            for field in new_class.declared_fields.values():  # same as .base_fields
                err_messages = field.error_messages
                for err_code, err_msg in err_messages.items():
                    if err_code in _default_error_messages:
                        err_messages[err_code] = _default_error_messages[err_code]
                    elif err_msg.endswith('.'):  # remove Django msg ending dot, if any:
                        err_messages[err_code] = err_msg[:-1]

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
            msg += ". See response data for details"
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
            docstr = get_field_docstring(field) if field else ""
            if docstr:
                stream.write(f'# {docstr}')
                stream.write('\n')
            yaml.dump({param_name: value},
                      stream=stream, Dumper=Dumper, default_flow_style=False)
            stream.write('\n')

        return stream.getvalue()

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


def _get_regionalizations() -> Iterable[tuple[str, str]]:
    return [(_.name, str(_)) for _ in models.Regionalization.objects.all()]


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
    regionalization = MultipleChoiceWildcardField(choices=_get_regionalizations,
                                                  label='The Seimsic Hazard '
                                                        'Source Regionalizations '
                                                        'to use',
                                                  required=False)

    # the key of `cleaned_data:dict` mapped to the regionalization-selected models:
    SHSR_MODELS_KEY = 'shsr_gsim'

    def clean(self):
        cleaned_data = super().clean()
        lon = cleaned_data.get('longitude', None)
        lat = cleaned_data.get('latitude', None)
        if lat is None or lon is None:
            return cleaned_data
        fields = ('gsim__name', 'regionalization__name', 'geometry')
        qry = models.GsimRegion.objects.\
            select_related('gsim', 'regionalization').\
            only(*fields).values_list(*fields)
        rgnz = cleaned_data['regionalization'] or []
        if rgnz:
            qry = qry.filter(regionalization__name__in=rgnz)
        gsims = set()
        point = Point(lon, lat)
        for gsim_name, regionalization_name, geometry in qry.all():
            if gsim_name in gsims:
                continue
            type, coords = geometry['type'], geometry['coordinates']
            for coord in coords if type == 'MultiPolygon' else [coords]:
                polygon = Polygon((tuple(l) for l in coord[0]))
                if polygon.contains(point):
                    gsims.add(gsim_name)
                    break
        if gsims:
            cleaned_data[self.SHSR_MODELS_KEY] = sorted(gsims)

        return cleaned_data


def _get_gsim_choices():  # https://stackoverflow.com/a/57809521
    return [(_, _) for _ in models.Gsim.objects.only('name').values_list('name',
                                                                         flat=True)]


def _get_imt_choices():  # https://stackoverflow.com/a/57809521
    return [(_, _) for _ in models.Imt.objects.only('name').values_list('name',
                                                                        flat=True)]


class GsimImtForm(SHSRForm):
    """Base abstract-like form for any form requiring Gsim+Imt selection"""

    # Custom API param names (see doc of `EgsimBaseForm._field2params` for details):
    _field2params: dict[str, list[str]] = {'gsim': ['model', 'gsim', 'gmm']}

    # Note: both Fields below are required actually (see `clean` for details):
    gsim = MultipleChoiceWildcardField(required=False, choices=_get_gsim_choices)
    imt = ImtField(required=False, choices=_get_imt_choices,
                   label='Intensity Measure Type(s)')

    def clean(self):
        """Run validation where we must validate selected gsim(s) based on
        selected intensity measure type
        """
        gsim, imt = 'gsim', 'imt'
        cleaned_data = super().clean()

        # gsim is required but first check that we passed the lat, lon arguments,
        # in that case we might have already a list of gsim to merge with the
        # one provided via the classical gsim parameter
        regionalization_based_gsims = cleaned_data.pop(self.SHSR_MODELS_KEY, [])
        if regionalization_based_gsims:
            if cleaned_data.get(gsim, None):
                unique_gsims = sorted(set(list(cleaned_data[gsim]) +
                                          regionalization_based_gsims))
                cleaned_data[gsim] = unique_gsims
            else:
                cleaned_data[gsim] = regionalization_based_gsims

        # Check that both fields are provided. Another reason we do it here instead
        # than simply set `required=True` as Field argument is that sometimes
        # `MultipleChoiceField`s do not raise but puts a def. val, e.g. []
        if not self.accept_empty_gsims and \
                not cleaned_data.get(gsim, None) and not self.has_error(gsim):
            self.add_error(gsim,
                           ValidationError(self.fields[gsim].error_messages['required'],
                                           code='required'))
        if not self.accept_empty_imts and \
                not cleaned_data.get(imt, None) and not self.has_error(imt):
            self.add_error(imt,
                           ValidationError(self.fields[imt].error_messages['required'],
                                           code='required'))
        # if any of the if above was true, then the parameter has been removed from
        # cleaned_data. If both are provided, check gsims and imts match:
        if not self.has_error(gsim) and not self.has_error(imt):
            self.validate_gsim_and_imt(cleaned_data[gsim], cleaned_data[imt])
        return cleaned_data

    accept_empty_gsims = False  # override in subclasses if you accept emopty gsims
    accept_empty_imts = False  # see above (for imts)

    def validate_gsim_and_imt(self, gsims, imts):
        """Validate gsim and imt assuring that all gsims are defined for all
        supplied imts, and all imts are defined for all supplied gsim.
        This method calls self.add_error and works on self.cleaned_data, thus
        it should be called after super().clean()
        """
        # (gsims and imts are both validated, non empty lists)
        # we want imt class names merge all SA(...) as one single 'SA'
        has_sa = any(i.startswith('SA') for i in imts)
        if has_sa:
            imts = ['SA'] + [i for i in imts if not i.startswith('SA')]

        invalid_gsims = set(gsims) - set(self.sharing_gsims(imts))

        if invalid_gsims:
            # For details see "cleaning and validating fields that depend on each other"
            # on the django doc:
            invalid_imts = set(imts) - set(self.shared_imts(gsims))
            code = 'invalid_model_imt_combination'
            err_gsim = ValidationError(f"{len(invalid_gsims)} model(s) not defined "
                                       "for all supplied imt(s)", code=code)
            err_imt = ValidationError(f"{len(invalid_imts)} imt(s) not defined for "
                                      "all supplied model(s)", code=code)
            # add_error removes also the field from self.cleaned_data:
            gsim, imt = 'gsim', 'imt'
            self.add_error(gsim, err_gsim)
            self.add_error(imt, err_imt)

    @staticmethod
    def shared_imts(gsim_names):
        """Returns a list of IMT names shared by *all* the given GSIMs

        :param gsim_names: list of strings denoting GSIM names
        """
        if not gsim_names:
            return []

        # https://stackoverflow.com/a/8637972
        objs = models.Imt.objects  # noqa
        for gsim in gsim_names:
            objs = objs.filter(gsims__name=gsim)

        return objs.values_list('name', flat=True).distinct()

    @staticmethod
    def sharing_gsims(imt_names):
        """Returns a list of GSIM names sharing *all* the given IMTs

        :param imt_names: list of strings denoting GSIM names
        """
        if not imt_names:
            return []

        # https://stackoverflow.com/a/8637972
        objs = models.Gsim.objects  # noqa
        for imtx in imt_names:
            objs = objs.filter(imts__name=imtx)

        return objs.values_list('name', flat=True).distinct()


class APIForm(EgsimBaseForm):
    """Basic API Form: handle user request in different media types (json, text)
     and returning the relative response"""

    DATA_FORMAT_CSV = 'csv'
    DATA_FORMAT_JSON = 'json'

    _textcsv_sep = {
        'comma': ',',
        'semicolon': ';',
        'space': ' ',
        'tab': '\t'
    }

    _dec_sep = {
        'period': '.',
        'comma': ','
    }

    @property
    def data_format(self):
        return self.data['format']

    format = ChoiceField(required=True, initial=DATA_FORMAT_JSON,
                         label='The format of the returned data (server response)',
                         choices=[(DATA_FORMAT_JSON, 'json'),
                                  (DATA_FORMAT_CSV, 'text/csv')])

    csv_sep = ChoiceField(required=False, initial='comma',
                          choices=[(_, _) for _ in _textcsv_sep],
                          label='The (column) separator character',
                          help_text=('Ignored if the requested '
                                     'format is not text'))

    csv_dec = ChoiceField(required=False, initial='period',
                          choices=[(_, _) for _ in _dec_sep],
                          label='The decimal separator character',
                          help_text=('Ignored if the requested '
                                     'format is not text'))

    def clean(self):
        cleaned_data = super().clean()
        keys = 'format', 'csv_sep', 'csv_dec'
        if all(_ in cleaned_data for _ in keys):
            key, tsep, tdec = keys
            # convert to symbols:
            if cleaned_data[key] == self.DATA_FORMAT_CSV \
                    and cleaned_data[tsep] == cleaned_data[tdec]:
                msg = (f"'{tsep}' must differ from '{tdec}' in "
                       f"'{self.DATA_FORMAT_CSV}' format")
                err_ = ValidationError(msg, code='conflicting values')
                # add_error removes also the field from self.cleaned_data:
                self.add_error(tsep, err_)
                self.add_error(tdec, err_)
            else:
                cleaned_data[tsep] = self._textcsv_sep[cleaned_data[tsep]]
                cleaned_data[tdec] = self._dec_sep[cleaned_data[tdec]]

        return cleaned_data

    @property
    def response_data(self) -> Union[dict, StringIO, None]:
        """Return the response data by processing the form data, or None if
        the form is invalid (`self.is_valid() == False`)
        """
        if not self.is_valid():
            return None

        cleaned_data = self.cleaned_data
        obj = self.process_data(cleaned_data)
        if obj is None:
            obj = {}
        if self.data_format == self.DATA_FORMAT_CSV:
            obj = self.to_csv_buffer(obj, cleaned_data['csv_sep'],
                                     cleaned_data['csv_dec'])
        return obj

    @classmethod
    def process_data(cls, cleaned_data: dict) -> dict:
        """Process the input data `cleaned_data` returning the response data
        of this form upon user request.
        This method is called by `self.response_data` only if the form is valid.

        :param cleaned_data: the result of `self.cleaned_data`
        """
        raise NotImplementedError(":meth:%s.process_data" % cls.__name__)

    @classmethod
    def to_csv_buffer(cls, processed_data: dict, sep=',', dec='.') -> StringIO:
        """Convert the given processed data to a StringIO with CSV data
        as string

        :param processed_data: the output of `self.get_processed_data`
        :param sep: string default ',' the text separator
        :param dec: string default '.' the decimal separator
        """
        # code copied from: https://stackoverflow.com/a/41706831
        buffer = StringIO()  # python 2 needs io.BytesIO() instead
        wrt = csv.writer(buffer, delimiter=sep, quotechar='"',
                         quoting=csv.QUOTE_MINIMAL)

        # first build a list to get the maximum number of columns (for safety):
        rowsaslist = []
        maxcollen = 0
        comma_decimal = dec == ','
        for row in cls.csv_rows(processed_data):
            if not isinstance(row, list):
                row = list(row)
            if comma_decimal:
                # convert dot to comma in floats:
                for i, cell in enumerate(row):
                    if isinstance(cell, float):
                        row[i] = str(cell).replace('.', ',')
            rowsaslist.append(row)
            maxcollen = max(maxcollen, len(row))

        # Write matrix to csv. Pad each row with None (which will be written
        # as empty string, see csv doc. All non-string data are stringified
        # with str() before being written).
        wrt.writerows(chain(r, repeat(None, maxcollen - len(r)))
                      for r in rowsaslist)

        return buffer

    @classmethod
    def csv_rows(cls, processed_data) -> Iterable[Iterable[Any]]:
        """Yield CSV rows, where each row is an iterables of Python objects
        representing a cell value. Each row doesn't need to contain the same
        number of elements, the caller function `self.to_csv_buffer` will pad
        columns with Nones, in case (note that None is rendered as "", any other
        value using its string representation).

        :param processed_data: dict resulting from `self.process_data`
        """
        raise NotImplementedError(":meth:%s.csv_rows" % cls.__name__)


class GsimFromRegionForm(SHSRForm, APIForm):
    """API Form returning a list of models from a given location and optional
    seismic hazard source regionalizations (SHSR)"""

    @classmethod
    def process_data(cls, cleaned_data: dict) -> dict[str, str]:
        """Process the input data `cleaned_data` returning the response data
        of this form upon user request, ie.e a dict of gsim name mapped to its
        regionalization name.
        This method is called by `self.response_data` only if the form is valid.

        :param cleaned_data: the result of `self.cleaned_data`
        """
        return cleaned_data.get(SHSRForm.SHSR_MODELS_KEY, [])

    @classmethod
    def csv_rows(cls, processed_data) -> Iterable[Iterable[Any]]:
        """Yield CSV rows, where each row is an iterables of Python objects
        representing a cell value. Each row doesn't need to contain the same
        number of elements, the caller function `self.to_csv_buffer` will pad
        columns with Nones, in case (note that None is rendered as "", any other
        value using its string representation).

        :param processed_data: dict resulting from `self.process_data`
        """
        yield from processed_data


####################################
# Utilities shared among all Forms #
####################################

def relabel_sa(string):
    """Simplifies SA string representation removing redundant trailing zeros,
    if present. Examples:
    'SA(1)' -> 'SA(1)' (unchanged)
    'SA(1.0)' -> 'SA(1.0)' (unchanged)
    'ASA(1.0)' -> 'ASA(1.0)' (unchanged)
    'SA(1.00)' -> 'SA(1.0)'
    'SA(1.000)' -> 'SA(1.0)'
    'SA(.000)' -> 'SA(.0)'
    """
    return re.sub(r'((?:^|\s|\()SA\(\d*\.\d\d*?)0+(\))(?=($|\s|\)))', r"\1\2",
                  string)
