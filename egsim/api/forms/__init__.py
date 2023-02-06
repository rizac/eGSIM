"""Base eGSIM forms"""

import re
from django.forms.renderers import get_default_renderer
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
                     FloatField, get_field_docstring, NArrayField)
from .. import models


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


#########
# Forms #
#########


class EgsimFormMeta(DeclarativeFieldsMetaclass):
    """EGSIM Form metaclass. Inherits from `DeclarativeFieldsMetaclass` (base metaclass
    for all Django Forms) and sets up the defined field -> API params mappings
    """

    def __new__(mcs, name, bases, attrs):
        new_class = super().__new__(mcs, name, bases, attrs)
        # Attribute denoting field -> API params mappings:
        attname = '_field2params'
        # Dict denoting the field -> API params mappings:
        field2params = {}
        # Fill `field2params` with the superclass data:
        for base in bases:
            # Overwriting is safe, because same key (field) <=> same value (params):
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


class EgsimBaseForm(Form, metaclass=EgsimFormMeta):
    """Base eGSIM form"""

    # As we use Django as REST API only, we need no Django renderer. To avoid creating a
    # new renderer inside each Form `__init__`, we can tell Django to always use the same
    # renderer by instantiating it once with this class attribute:
    default_renderer = get_default_renderer()

    # Fields of this class are exposed as API request parameters via their attribute name
    # by default. Because attribute names must be immutable to avoid breaking the code
    # (e.g,, they are used as keys of `self.cleaned_data`) and parameter names should
    # be changed easily, the dict `_field2params` below allows to map a Field attribute
    # name to a list of parameter name(s) that can be used instead (including the same
    # Field attribute name, if needed). The first parameter name in the list will be
    # considered the default and displayed in e.g., missing param errors. `_field2params`
    # of superclasses will be merged into this one (see `EgsimFormMeta` metaclass). This
    # is a private-like attribute, to access all parameters and fields, use `apifields()`
    _field2params: dict[str, list[str]]

    # set of default error messages that will overwrite the Fields default as
    # dict[error_code:str, error_msg:str]
    _default_error_messages = {'required': 'This parameter is required'}

    def __init__(self, data=None, files=None, no_unknown_params=True, **kwargs):
        """Override init: re-arrange `self.data` and set the initial value for
        missing fields. Note that `data` might be modified inplace.
        In addition, This Form and subclasses ensure that all fields which have
        an initial value (not None) and do not get values from user get populated by
        their initial value

        :param data: the Form data (dict or None). Keys should be API parameters:
            the conversion to Field attribute names is done inside this method
        :param files: the Form files
        :param no_unknown_params: boolean indicating whether unknown parameters (`data`
            keys) should invalidate the Form. The default is True to prevent that
            parameters with an initial value set, if misspelled, take the initial value
            with no warnings
        """
        # remove colon in labels by default in templates:
        kwargs.setdefault('label_suffix', '')
        # store original dict:
        self._input_data = dict(data or {})
        # call super:
        super(EgsimBaseForm, self).__init__(data, files, **kwargs)

        # Fix self.data and store parameter errors in a list of ValidationErrors
        # (see `self.full_clean`and `self.validation_errors` for details):
        self._init_errors = []
        unknowns = set(self.data) if no_unknown_params else None
        for params, field_name, field in self.apifields():
            if unknowns is not None:
                unknowns -= set(params)
            input_params = tuple(p for p in params if p in self.data)
            if len(input_params) > 1:  # names conflict, store error:
                self._init_errors.append(ValidationError(",".join(input_params),
                                                         code='_conflict_egsim_param_'))
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

        if unknowns:  # unknown (nonexistent) parameters, store error:
            self._init_errors.append(ValidationError(",".join(unknowns),
                                                     code='_unknown_egsim_param_'))

        # Adjust Fields default error messages with our one, oif provided:
        for err_code, err_msg in self._default_error_messages.items():
            for field in self.fields.values():
                if err_code in field.error_messages:
                    field.error_messages[err_code] = err_msg

    def full_clean(self):
        """Performs a full clean of this form, but first check if we had initialization
        errors. In case, put them in `self._errors` and return"""
        if self._init_errors:
            self._errors = ErrorDict()
            self.cleaned_data = {}  # noqa
            for error in self._init_errors:
                self.add_error(None, error)
            return

        super().full_clean()  # re-initializes self._errors and self.cleaned_data

    def validation_errors(self, msg: str = None) -> dict:
        """Reformat `self.errors.as_json()` into the following dict (all keys and values
        are strings):
        ```
        {
            "message": `msg` or an auto generated message (see below for details)
            "errors": [
                {
                    "location": parameter name,
                    "message": detailed error message,
                    "reason": error code, e.g. 'invalid', 'required', 'conflict'
                }
                ...
            ]
        }
        ```
        NOTE: This method should be called if `self.is_valid()` returns False

        :param msg: the global error message. If None, it defaults to a general
            message with the list of parameters with problems (if any is found)

        For details see:
        https://cloud.google.com/storage/docs/json_api/v1/status-codes
        https://google.github.io/styleguide/jsoncstyleguide.xml
        """
        errors_dict: dict[str, list[dict[str, str]]] = self.errors.get_json_data()
        if not errors_dict:
            return {}

        field2param = {field_name: params for params, field_name, _ in self.apifields()}

        errors = []
        err_param_names = set()
        # build errors dict:
        for field_name, errs in errors_dict.items():
            param_name = None
            if field_name in field2param:
                def_param_names = field2param[field_name]
                input_param_names = [p for p in def_param_names if p in self._input_data]
                param_name = (input_param_names or def_param_names)[0]
            if param_name is not None:
                err_param_names.add(param_name)
            # compose dict for detailed error messages:
            for err in errs:
                err_message = err.get('message', '')
                err_code = err.get('code', '')
                # if we have an unknown egsim message, add the unknown parameters in
                # the main message header:
                pnames = err_message.split(",")
                if err_code == "_conflict_egsim_param_":
                    err_param_names.add("/".join(pnames))
                    for pname in pnames:
                        others = ", ".join(p for p in pnames if p != pname)
                        # store detailed error info as dict:
                        errors.append({
                            'location': pname,
                            'message': f"This parameter conflicts with: {others}",
                            'reason': "conflict"
                        })
                elif err_code == "_unknown_egsim_param_":
                    for pname in pnames:
                        err_param_names.add(pname)
                        # store detailed error info as dict:
                        errors.append({
                            'location': pname,
                            'message': "This parameter does not exist (check typos)",
                            'reason': "nonexistent"
                        })
                else:
                    errors.append({
                        'location': param_name or 'unspecified',
                        'message': err_message,
                        'reason': err_code
                    })

        if not msg:
            msg = "Invalid request"
            if err_param_names:
                msg += f'. Problems found in: {", ".join(sorted(err_param_names))}'
            msg += ". See response data for details"
        return {
            'message': msg,
            'errors': errors
        }

    @classmethod
    def apifields(cls) -> Iterable[tuple[list[str, ...], str, Field]]:
        """Yield the Fields of this class as tuples of 3 elements:
        ```
        params: list[str], field_name: str, field: Field
        ```
        where `params` is a list of API parameter names of the Field (1st param is the
        default), and it is usually a list with the field name as only element,
        unless different parameter name(s) are provided in `self._field2params`
        """
        for field_name, field in cls.declared_fields.items():
            params = cls._field2params.get(field_name, [field_name])
            yield params, field_name, field

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
        param2field = {
            p_name: field for p_names, _, field in self.apifields() for p_name in p_names
        }
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
        if not cleaned_data.get(gsim, None) and not self.has_error(gsim):
            self.add_error(gsim,
                           ValidationError(self.fields[gsim].error_messages['required'],
                                           code='required'))
        if not cleaned_data.get(imt, None) and not self.has_error(imt):
            self.add_error(imt,
                           ValidationError(self.fields[imt].error_messages['required'],
                                           code='required'))
        # if any of the if above was true, then the parameter has been removed from
        # cleaned_data. If both are provided, check gsims and imts match:
        if not self.has_error(gsim) and not self.has_error(imt):
            self.validate_gsim_and_imt(cleaned_data[gsim], cleaned_data[imt])
        return self.cleaned_data

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
            # instead of raising ValidationError, which is keyed with
            # '__all__' we add the error keyed to the given field name
            # `name` via `self.add_error`:
            # https://docs.djangoproject.com/en/stable/ref/forms/validation/
            # #cleaning-and-validating-fields-that-depend-on-each-other
            # note: pass only invalid_gsims as the result would be equal
            # than passing all gsims but the loop is faster:
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
        obj = self.process_data(cleaned_data) or {}  # assure is not None
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
