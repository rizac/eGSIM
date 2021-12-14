from collections import defaultdict
from typing import Union, Iterable, Any
import json
from itertools import chain, repeat
from io import StringIO
import csv

from django.core.exceptions import ValidationError
from django.utils.translation import gettext
from django.forms import Form
from .fields import MultipleChoiceWildcardField, ImtField, ChoiceField
from .. import models


class EgsimBaseForm(Form):
    """Base eGSIM form"""

    # For each Field of this Form: the attribute name MUST NOT CHANGE, because
    # code relies on it (see e.g. keys of `cleaned_data`). The attribute value
    # can change as long as it inherits from `egsim.forms.fields.ParameterField`

    def __init__(self, *args, **kwargs):
        """Override init to set custom attributes on field widgets and to set
        the initial value for fields of this class with no match in the keys
        of `self.data`
        """
        # remove colon in labels by default in templates:
        kwargs.setdefault('label_suffix', '')
        # call super:
        super(EgsimBaseForm, self).__init__(*args, **kwargs)

        # Re-arrange input data (`self.data`)
        fields = self.fields
        # Create a first mapping from field attribute names to parameter names:
        self._inputparam_name = {n: f.names[0] for n, f in fields.items()}
        # Now replace parameter names (keys of `self.data`) with the corresponding
        # field attribute name, if any, and in case update `self._inputparam_name`:
        nonfield_params = set(k for k in self.data if k not in fields)
        if nonfield_params:
            parameter_names = self.parameter_names()
            for nonfield_param in nonfield_params & set(parameter_names):
                field_name = parameter_names[nonfield_param]
                self.data[field_name] = self.data.pop(nonfield_param)
                self._inputparam_name[field_name] = nonfield_param

        # Make fields initial value the default (for details see discussion and
        # code example at https://stackoverflow.com/a/20309754):
        for name, field in fields.items():
            if name not in self.data and field.initial is not None:
                self.data[name] = field.initial

    @classmethod
    def parameter_names(cls) -> dict[str, str]:
        """dict mapping all parameter names to the Form field name"""
        # Every Field F is mapped to several parameter names N1, N2. Return
        # here a dict of N -> F. In case of duplicated keys: if there a field
        # named N, use that as key discarding others, otherwise raise ValueError
        fields = cls.declared_fields
        ret = {f: f for f in fields if any(n == f for n in fields[f].names)}
        duplicates = defaultdict(list)
        for field_name, field in fields.items():
            for param_name in field.names:
                if param_name in ret:
                    continue
                duplicates[param_name].append(field_name)
                ret[param_name] = field_name
        for p, fields in duplicates.items():
            if len(fields) > 1:
                raise ValueError(f'Parameter name conflict: "{p}" is set for '
                                 f'several form fields: {", ".join(fields)}')
        return ret

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
        errors = []
        pnames = []
        for key, values in dic.items():
            # get the param name as input by the user:
            input_param_name = self._inputparam_name.get(key, key)
            # add the name to be displayed in the global msg (see below):
            pnames.append(input_param_name)
            # compose dict for detailed error messages:
            for value in values:
                errors.append({'location': input_param_name,
                               'message': value.get('message', ''),
                               'reason': value.get('code', '')})

        if not msg:
            msg = f'Invalid parameter{"" if len(pnames) == 1 else "s"}: ' \
                  f'{", ".join(pnames)}'

        return {
            'message': msg,
            'errors': errors
        }


def get_gsim_choices():  # https://stackoverflow.com/a/57809521
    return [(_, _) for _ in models.Gsim.objects.values_list('name', flat=True)]


def get_imt_choices():  # https://stackoverflow.com/a/57809521
    return [(_, _) for _ in models.Imt.objects.values_list('name', flat=True)]


class GsimImtForm(EgsimBaseForm):
    """Base abstract-like form for any form requiring Gsim+Imt selection"""

    # For each Field of this Form: the attribute name MUST NOT CHANGE, because
    # code relies on it (see e.g. keys of `cleaned_data`). The attribute value
    # can change as long as it inherits from `egsim.forms.fields.ParameterField`

    gsim = MultipleChoiceWildcardField('gsim', 'gmm', 'gmpe',
                                       required=True, choices=get_gsim_choices,
                                       label='Ground Shaking Intensity Model(s)')
    imt = ImtField('imt',
                   required=True, choices=get_imt_choices,
                   label='Intensity Measure Type(s)')

    def clean(self):
        """Run validation where we must validate selected gsim(s) based on
        selected intensity measure type
        """
        cleaned_data = super().clean()
        gsim, imt = 'gsim', 'imt'
        # for safety, check both are provided (with some field settings Django
        # might append a falsy value if missing, e.g. [], which we do not want):
        if gsim in cleaned_data and not cleaned_data[gsim]:
            self.add_error(gsim, ValidationError('Missing gsim(s)', code='required'))
        if imt in cleaned_data and not cleaned_data[imt]:
            self.add_error(imt, ValidationError('Missing imt(s)', code='required'))
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

    # For each Field of this Form: the attribute name MUST NOT CHANGE, because
    # code relies on it (see e.g. keys of `cleaned_data`). The attribute value
    # can change as long as it inherits from `egsim.forms.fields.ParameterField`

    format = ChoiceField('format', 'data_format',
                         required=True, initial=DATA_FORMAT_JSON,
                         label='The format of the data returned (response data)',
                         choices=[(DATA_FORMAT_JSON, 'json'),
                                  (DATA_FORMAT_CSV, 'text/csv')])

    csv_sep = ChoiceField('csv_sep',
                          required=False, initial='comma',
                          choices=[(_, _) for _ in _textcsv_sep],
                          label='The (column) separator character',
                          help_text=('Ignored if the requested '
                                     'format is not text'))

    csv_dec = ChoiceField('csv_dec',
                          required=False, initial='period',
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


class APIForm(GsimImtForm, MediaTypeForm):
    """GsimImtForm + MediaTypeForm"""

    # For each Field of this Form: the attribute name MUST NOT CHANGE, because
    # code relies on it (see e.g. keys of `cleaned_data`). The attribute value
    # can change as long as it inherits from `egsim.forms.fields.ParameterField`

    def clean(self):
        """Calls GsimImtForm and MediaTypeForm, useful in subclasses to avoid
        calling twice the same super method?"""
        return super().clean()

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
    def processed_data_as_csv(cls,  processed_data: dict, sep=',', dec='.'):
        return cls.to_csv_buffer(processed_data, sep, dec).getvalue()

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
