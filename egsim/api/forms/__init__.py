"""Base eGSIM forms"""

import re
from typing import Union, Iterable, Any
import json
from itertools import chain, repeat
from io import StringIO
import csv

from shapely.geometry import Polygon, Point
from django.core.exceptions import ValidationError
from django.forms.forms import DeclarativeFieldsMetaclass  # noqa
from django.utils.translation import gettext
from django.forms import Form

from .fields import (MultipleChoiceWildcardField, ImtField, ChoiceField, Field,
                     FloatField)
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
    """Inherits from Django Form Metaclass: call superclass (see source) and
    then setup the Form class public field names
    """

    def __new__(mcs, name, bases, attrs):
        new_class = super().__new__(mcs, name, bases, attrs)

        attname = '_field2params'
        # Walk through the MRO to merge all dicts
        field2params = {}
        for cls in reversed(new_class.__mro__):
            field2params.update(getattr(cls, attname, {}))

        # Check1: no param provided twice or more:
        _done_params = set()
        for field, params in field2params.items():
            if set(params) & _done_params:
                raise ValueError(f"Error in `{name}.{attname}['{field}']={params}:"
                                 f"{', '.join(set(params) & _done_params)} already "
                                 f"provided")
            _done_params.update(params)

        # Check2: no param equal to another field name
        cls_fields = set(new_class.declared_fields)
        for field, params in field2params.items():
            for p in params:
                if p != field and p in cls_fields:
                    raise ValueError(f"Error in `{name}.{attname}['{field}']={params}:"
                                     f"`{p}` denotes another Field name")

        # Check 3: all values must be list or tuples:
        for field in list(field2params):
            params = field2params[field]
            if not isinstance(params, tuple):
                if isinstance(params, list):
                    field2params[field] = tuple(params)
                else:
                    raise ValueError(f"Error in `{name}.{attname}['{field}']={params}:"
                                     f"`dict values must be lists or tuples")

        # assign new dict of public field name:
        setattr(new_class, attname, field2params)
        return new_class


class EgsimBaseForm(Form, metaclass=EgsimFormMeta):
    """Base eGSIM form"""

    # Fields of this class are exposed as API parameters via their attribute name. This
    # default behaviour can be changed here by manually mapping a Field attribute name to
    # its API param name(s). `_field2params` allows to easily change API params whilst
    # keeping the Field attribute names immutable, which is needed to avoid breaking the
    # code. See `egsim.forms.EgsimFormMeta` for details and `self.apifields()`
    _field2params: dict[str, list[str]]

    def __init__(self, data=None, files=None, no_unknown_params=True, **kwargs):
        """Override init: re-arrange `self.data` and set the initial value for
        missing fields
        """
        # remove colon in labels by default in templates:
        kwargs.setdefault('label_suffix', '')
        # call super:
        super(EgsimBaseForm, self).__init__(data, files, **kwargs)

        # Replace keys of `self.data` (input params) with the field names, when
        # needed (see `_field2params`), and do some check:
        self._renamed_fields = {}  # keep track of what will be replaced
        for field_name, param_names in self._field2params.items():
            if field_name in self.data:
                continue
            params = [p for p in param_names if p in self.data]
            if not params:
                continue
            elif len(params) > 1:
                raise ValidationError('Conflicting parameter names: '
                                      f'{", ".join(params)}')
            self._renamed_fields[field_name] = params[0]
            self.data[field_name] = self.data.pop(params[0])

        # check unknown parameters provided by the user:
        if no_unknown_params and (set(self.data) - set(self.declared_fields)):
            err_names = set(self.data) - set(self.declared_fields)
            raise ValidationError(f'Unknown parameter'
                                  f'{"s" if len(err_names) != 1 else ""}: '
                                  f'{", ".join(err_names)}')

        # Make fields initial value the default (for details see discussion and
        # code example at https://stackoverflow.com/a/20309754):
        for name, field in self.fields.items():
            if name not in self.data and field.initial is not None:
                self.data[name] = field.initial

    def validation_errors(self, msg: str = None) -> dict:
        """Reformat `self.errors.as_json()` into the following dict:
        ```
        {
            "message": `msg` or, if None, "Invalid parameter(s) " + param. list
            "errors": [
                {
                    "location": param. name (str),
                    "message": error message (str),
                    "reason": error code, e.g. 'invalid', 'required', 'conflict' (str)
                }
                ...
            ]
        }
        ```
        NOTE: This method should be called if `self.is_valid()` returns False

        :param msg: the global error message. If None, it defaults to
            "Invalid parameter: " + param_name or
            "Invalid parameters: " + comma separated list of param names

        For details see:
        https://cloud.google.com/storage/docs/json_api/v1/status-codes
        https://google.github.io/styleguide/jsoncstyleguide.xml
        """
        dic = json.loads(self.errors.as_json())
        if not dic:
            return {}
        errors = []

        err_param_names = []
        # build errors dict:
        for err_field_name, errs in dic.items():
            err_param_name = self._renamed_fields.get(err_field_name, err_field_name)
            err_param_names.append(err_param_name)
            # compose dict for detailed error messages:
            for err in errs:
                errors.append({'location': err_param_name,
                               'message': err.get('message', ''),
                               'reason': err.get('code', '')})

        if not msg:
            msg = f'Invalid parameter{"" if len(err_param_names) == 1 else "s"}: ' \
                  f'{", ".join(err_param_names)}'

        return {
            'message': msg,
            'errors': errors
        }

    @classmethod
    def apifields(cls) -> Iterable[tuple[list[str, ...], str, Field]]:
        """Yields the Fields of this form as tuples of

        (API parameter name(s) of the field, field name, Field object).

        By default, the API parameter name(s) is trivially a list with the
        field name as only element. This is not the case for Field names mapped
        to different API parameter names in `self._field2params`
        """
        for field_name, field in cls.declared_fields.items():
            params = cls._field2params.get(field_name, [field_name])
            yield params, field_name, field


def _get_regionalizations() -> Iterable[tuple[str, str]]:
    return [(_.name, str(_)) for _ in models.Regionalization.objects.all()]


class SHSRForm(EgsimBaseForm):
    """Base class for all Form accepting a list of models in form of location
    (lat lon) and optional list of seismic hazard source regionalizations (SHSR)"""

    # Fields of this class are exposed as API parameters via their attribute name. This
    # default behaviour can be changed here by manually mapping a Field attribute name to
    # its API param name(s). `_field2params` allows to easily change API params whilst
    # keeping the Field attribute names immutable, which is needed to avoid breaking the
    # code. See `egsim.forms.EgsimFormMeta` for details
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

    # Fields of this class are exposed as API parameters via their attribute name. This
    # default behaviour can be changed here by manually mapping a Field attribute name to
    # its API param name(s). `_field2params` allows to easily change API params whilst
    # keeping the Field attribute names immutable, which is needed to avoid breaking the
    # code. See `egsim.forms.EgsimFormMeta` for details
    _field2params: dict[str, list[str]] = {'gsim': ['model', 'gmm']}

    # Note: both Fields below are required actually (see `clean` for details):
    gsim = MultipleChoiceWildcardField(required=False, choices=_get_gsim_choices,
                                       label='Ground Shaking Intensity Model(s)')
    imt = ImtField(required=False, choices=_get_imt_choices,
                   label='Intensity Measure Type(s)')

    def clean(self):
        """Run validation where we must validate selected gsim(s) based on
        selected intensity measure type
        """
        gsim, imt = 'gsim', 'imt'

        # gsim is required but first check that we passed the lat, lon arguments,
        # in that case we might have already a list of gsim to merge with the
        # one provided via the classical gsim parameter
        cleaned_data = super().clean()
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
        if not cleaned_data.get(gsim, None):
            self.add_error(gsim, ValidationError('Missing value', code='required'))
        if not cleaned_data.get(imt, None):
            self.add_error(imt, ValidationError('Missing value', code='required'))
        # if any of the if above was true, then the parameter has been removed from
        # cleaned_data. If both are provided, check gsims and imts match:
        if gsim in cleaned_data and imt in cleaned_data:
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
        len_ = len(imts)
        imts = [i for i in imts if not i.startswith('SA')]
        if len(imts) < len_:
            imts += ['SA']

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
            err_gsim = ValidationError(gettext("%(num)d gsim(s) not defined "
                                               "for all supplied imt(s)"),
                                       params={'num': len(invalid_gsims)},
                                       code='invalid')
            err_imt = ValidationError(gettext("%(num)d imt(s) not defined for "
                                              "all supplied gsim(s)"),
                                      params={'num': len(invalid_imts)},
                                      code='invalid')
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


class MediaTypeForm(EgsimBaseForm):
    """Form handling the validation of the format related argument in a request"""

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
                         label='The format of the data returned (response data)',
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
                msg = gettext(f"'{tsep}' must differ from '{tdec}' in "
                              f"'{self.DATA_FORMAT_CSV}' format")
                err_ = ValidationError(msg, code='conflicting values')
                # add_error removes also the field from self.cleaned_data:
                self.add_error(tsep, err_)
                self.add_error(tdec, err_)
            else:
                cleaned_data[tsep] = self._textcsv_sep[cleaned_data[tsep]]
                cleaned_data[tdec] = self._dec_sep[cleaned_data[tdec]]

        return cleaned_data


class APIForm(MediaTypeForm):
    """GsimImtForm + MediaTypeForm"""

    @property
    def response_data(self) -> Union[dict, StringIO, None]:
        """Return the response data by processing the form data, or None if
        the form is invalid (`self.is_valid() == False`)
        """
        if not self.is_valid():
            return None

        cleaned_data = self.cleaned_data
        obj = self.process_data(cleaned_data) or {}  # assure is not None
        if self.data_format == MediaTypeForm.DATA_FORMAT_CSV:
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
