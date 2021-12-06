from fnmatch import translate
from typing import Union, Iterable, Any
import re
import json
import shlex
from itertools import chain, repeat
from io import StringIO
import csv

import numpy as np
from django.db.models import Q
from openquake.hazardlib import imt
from django.core.exceptions import ValidationError
from django.utils.translation import gettext
from django.forms import Form
from django.forms.fields import (CharField, ChoiceField, MultipleChoiceField)

from .. import models

##########
# Fields #
##########


class ArrayField(CharField):
    """Django CharField subclass which parses and validates string inputs given
    as array of elements in JSON (comma separated variables, with optional
    square brackets) or Unix shell (space separated variables) syntax.
    The type of the parsed elements depends on `self.parse(token)` which by
    default returns `token` but might be overridden by subclasses (see
    :class:`NArrayField`).
    As Form fields act also as validators, an object of this class can deal
    also with already parsed (e.g. via YAML) arrays
    """
    def __init__(self, *, min_count=None, max_count=None,
                 min_value=None, max_value=None, **kwargs):
        """Initialize a new ArrayField
         :param min_count: numeric or None. The minimum required count of the
             elements of the parsed array. Note that `min_length` is already
             defined in the super-class. If None (the default), parsed array
             can have any minimum length >=0.
         :param max_count: numeric or None. The maximum required count of the
             elements of the parsed array. Note that `max_length` is already
             defined in the super-class. If None (the default), parsed array
             can have any maximum length >=0.
         :param min_value: object. The minimum possible value for the
             elements of the parsed array. If None (the default) do not impose
             any minimum value. If iterable, sets the minimum required value
             element-wise (padding with None or slicing in case of lengths
             mismatch)
         :param max_value: object. Self-explanatory. Behaves the same as
             `min_value`
         :param kwargs: keyword arguments forwarded to the Django super-class.
        """
        # Parameters after “*” or “*identifier” are keyword-only parameters
        # and may only be passed used keyword arguments.
        super(ArrayField, self).__init__(**kwargs)
        self.min_count = min_count
        self.max_count = max_count
        self.min_value = min_value
        self.max_value = max_value

    def to_python(self, value):
        # three scenarios: iterable: take iterable
        # non iterable: parse [value]
        # string: split value into iterable
        values = []
        is_vector = not isscalar(value)

        if value is not None:
            if not is_vector and isinstance(value, str):
                value = value.strip()
                is_vector = value[:1] == '['
                if is_vector != (value[-1:] == ']'):
                    raise ValidationError('unbalanced brackets')
                try:
                    value = json.loads(value if is_vector else "[%s]" % value)
                except Exception:  # noqa
                    try:
                        value = shlex.split(value[1:-1].strip() if is_vector
                                            else value)
                    except Exception:
                        raise ValidationError('Input syntax error')

            for val in vectorize(value):
                try:
                    vls = self.parse(val)
                except ValidationError:
                    raise
                except Exception as exc:
                    raise ValidationError("%s: %s" % (str(val), str(exc)))

                if isscalar(vls):
                    values.append(vls)
                else:
                    # force the return value to be list even if we have 1 elm:
                    is_vector = True
                    values.extend(vls)

            # check lengths:
            try:
                self.checkrange(len(values), self.min_count, self.max_count)
            except ValidationError as verr:
                # just re-format exception string and raise:
                # msg should be in the form '% not in ...', remove first '%s'
                msg = verr.message[verr.message.find(' '):]
                raise ValidationError('number of elements (%d) %s' %
                                      (len(values), msg))

            # check bounds:
            minval, maxval = self.min_value, self.max_value
            minval = [minval] * len(values) if isscalar(minval) else minval
            maxval = [maxval] * len(values) if isscalar(maxval) else maxval
            for numval, mnval, mxval in zip(values,
                                            chain(minval, repeat(None)),
                                            chain(maxval, repeat(None))):
                self.checkrange(numval, mnval, mxval)

        return values[0] if (len(values) == 1 and not is_vector) else values

    @classmethod
    def parse(cls, token):
        """Parse token and return either an object or an iterable of objects.
        This method can safely raise any exception, if not ValidationError
        it will be wrapped into a suitable ValidationError
        """
        return token

    @staticmethod
    def checkrange(value, minval=None, maxval=None):
        """Check that the given value is in the range defined by `minval` and
        `maxval` (endpoints are included). None in `minval` and `maxval` mean:
        do not check. This method does not return any value but raises
        `ValidationError`` if value is not in the given range
        """
        toolow = (minval is not None and value < minval)
        toohigh = (maxval is not None and value > maxval)
        if toolow and toohigh:
            raise ValidationError('%s not in [%s, %s]' %
                                  (str(value), str(minval), str(maxval)))
        if toolow:
            raise ValidationError('%s < %s' % (str(value), str(minval)))
        if toohigh:
            raise ValidationError('%s > %s' % (str(value), str(maxval)))


class NArrayField(ArrayField):
    """ArrayField for sequences of numbers"""

    @staticmethod
    def float(val):
        """Wrapper around the built-in `float` function.
        Raises ValidationError in case of errors"""
        try:
            return float(val)
        except ValueError:
            raise ValidationError("Not a number: '%s'" % val)
        except TypeError:
            raise ValidationError(("input must be string(s) or number(s), "
                                   "not '%s'") % str(val))

    @classmethod
    def parse(cls, token):
        """Parse `token` into float.
        :param token: A python object denoting a token to be pared
        """
        # maybe already a number? try adn return
        try:
            return cls.float(token)
        except ValidationError:
            # raise if the input was not string: we surely can not deal it:
            if not isinstance(token, str):
                raise

        # Let's try the only option left, i.e. token is a range in matlab
        # syntax, e.g.: "1:3" = [1,2,3],  "1:2:3" = [1,3]
        spl = [_.strip() for _ in token.split(':')]
        if len(spl) < 2 or len(spl) > 3:
            if ':' in token:
                raise ValidationError("Expected format '<start>:<end>' or "
                                      "'<start>:<step>:<end>', found: '%s'"
                                      % token)
            raise ValidationError("Unparsable string '%s'" % token)

        start, step, stop = \
            cls.float(spl[0]), 1 if len(spl) == 2 else \
            cls.float(spl[1]), cls.float(spl[-1])
        decimals = cls.get_decimals(*spl)

        arange = np.arange(start, stop, step, dtype=float)
        if decimals is not None:
            if round(arange[-1].item() + step, decimals) == \
                    round(stop, decimals):
                arange = np.append(arange, stop)

            arange = np.round(arange, decimals=decimals)
            if decimals == 0:
                arange = arange.astype(int)
        return arange.tolist()

    @classmethod
    def get_decimals(cls, *strings):
        """parse each string and returns the maximum number of decimals
        :param strings: a sequence of strings. Note that they do not need to
        be parsable as floats, this method searches for the dot and the
        letter 'E' (ignoring case)
        """
        decimals = 0
        try:
            for string in strings:
                idx_dec = string.find('.')
                idx_exp = string.lower().find('e')
                if idx_dec > idx_exp > -1:
                    raise ValueError()  # stop parsing
                dec1 = 0 if idx_dec < 0 else \
                    len(string[idx_dec+1: None if idx_exp < 0 else idx_exp])
                dec2 = 0 if idx_exp < 0 else -int(string[idx_exp+1:])
                decimals = max([decimals, dec1 + dec2])
            # return 0 as we do not care for big numbers (they are int anyway)
            return decimals
        except ValueError:
            return None


class MultipleChoiceWildcardField(MultipleChoiceField):
    """Extension of Django MultipleChoiceField:
     - Accepts lists of strings or a single string
    (which will be converted to a 1-element list)
    - Accepts wildcard in strings in order to include all matching elements
    """

    def to_python(self, value):
        """convert strings with wildcards to matching elements, and calls the
        super method with the converted value. For valid wildcard characters,
        see https://docs.python.org/3.4/library/fnmatch.html"""
        # value might be None, string, list
        if value and isinstance(value, str):
            value = [value]  # no need to call super
        else:
            # `super.to_python` basically checks that `value` is not some weird
            # object, and returns a list of strings. It DOES NOT check yet if
            # any item in `value` in the possible choices (`self.validate` will
            # do that, later)
            value = super(MultipleChoiceWildcardField, self).to_python(value)

        if not any(MultipleChoiceWildcardField.has_wildcards(_) for _ in value):
            return value

        # Convert wildcard strings. Put them in a dict keys first, to avoid
        # duplicates and preserve the original list order (we are in py>=3.7)
        new_value = {}
        for val in value:
            if MultipleChoiceWildcardField.has_wildcards(val):
                reg = MultipleChoiceWildcardField.to_regex(val)
                for choice, _ in self.choices:
                    if reg.match(str(choice)):
                        new_value[choice] = None  # None or whatever, it's irrelevant
            else:
                new_value[val] = None   # None or whatever, it's irrelevant
        return list(new_value)

    @staticmethod
    def has_wildcards(string):
        return '*' in string or '?' in string or ('[' in string and ']' in string)

    @staticmethod
    def to_regex(value):
        """Convert string (a unix shell string, see
        https://docs.python.org/3/library/fnmatch.html) to regexp. The latter
        will match accounting for the case (ignore case off)
        """
        return re.compile(translate(value))


# https://docs.djangoproject.com/en/2.0/ref/forms/fields/#creating-custom-fields
class ImtField(MultipleChoiceWildcardField):
    """Field for IMT class selection. Provides a further validation for
    SA which is provided as (or with) periods (se meth:`valid_value`)
    """

    def valid_value(self, value):
        """Validate the given *single* imt `value`"""
        try:
            # use openquake first (e.g.  '0.2' -> 'SA(0.2)')
            value = imt.from_string(value).string
            # get function name (handle "SA(" case):
            value = value[:None if '(' not in value else value.index('(')]
        except Exception:  # noqa
            return False

        return super().valid_value(value)


#########
# Forms #
#########


class EgsimBaseForm(Form):
    """Base eGSIM form"""

    def fieldname_aliases(self, mapping):
        """Call `super()` and then for any field alias: `mapping[new_name]=name`
        Each new name will be used as request parameter alias, if this Form is
        used to validate API requests. See `EgsimBaseForm.__init__` for details
        """
        pass

    def __init__(self, *args, **kwargs):
        """Override init to set custom attributes on field widgets and to set
        the initial value for fields of this class with no match in the keys
        of `self.data`
        """
        # remove colon in labels by default in templates:
        kwargs.setdefault('label_suffix', '')
        # call super:
        super(EgsimBaseForm, self).__init__(*args, **kwargs)

        # now we want to re-name potential parameter names (e.g., 'mag' into
        # 'magnitude'):
        repl_dict = {}
        self.fieldname_aliases(repl_dict)
        for alias in set(repl_dict) & set(self.data):
            real_name = repl_dict[alias]
            self.data[real_name] = self.data.pop(alias)

        # Make fields initial value the default (for details see discussion and
        # code exmple at https://stackoverflow.com/a/20309754):
        for name in self.fields:
            if name not in self.data and  self.fields[name].initial is not None:
                self.data[name] = self.fields[name].initial

    def clean(self):
        """Same as super().clean(), overridden only to make subclasses
        implementation easier to discover in PyCharm"""
        return super().clean()

    def validation_errors(self, code=400,
                          msg_format='Invalid input in %(names)s') -> dict:
        """Convert `self.errors.as_json()` into a list of dicts
        formatted according to the Google format
        (https://google.github.io/styleguide/jsoncstyleguide.xml):
        ```
        {
            'message': str,
            'code': int,
            'errors': [
                {'domain': <str>, 'message': <str>, 'reason': <str>}
                ...
            ]
        }
        ```
        This method should be called if `self.is_valid()` returns False
        """
        dic = json.loads(self.errors.as_json())
        errors = []
        fields = []
        for key, values in dic.items():
            fields.append(key)
            for value in values:
                errors.append({'domain': key,
                               'message': value.get('message', ''),
                               'reason': value.get('code', '')})

        msg = msg_format % {'names': ', '.join(fields)}
        return {
            'message': msg,
            'code': code,
            'errors': errors
        }


def get_gsim_choices():  # https://stackoverflow.com/a/57809521
    return [(_, _) for _ in models.Gsim.objects.values_list('name', flat=True)]


def get_imt_choices():  # https://stackoverflow.com/a/57809521
    return [(_, _) for _ in models.Imt.objects.values_list('name', flat=True)]


class GsimImtForm(EgsimBaseForm):
    """Base abstract-like form for any form requiring Gsim+Imt selection"""

    def fieldname_aliases(self, mapping):
        """Set field name aliases (exposed to the user as API parameter aliases):
        call `super()` and then for any field alias: `mapping[new_name]=name`
        See `EgsimBaseForm.__init__` for details
        """
        super().fieldname_aliases(mapping)
        mapping['gmpe'] = 'gsim'
        mapping['gmm'] = 'gsim'

    gsim = MultipleChoiceWildcardField(required=True, choices=get_gsim_choices,
                                       label='Ground Shaking Intensity Model(s)')
    imt = ImtField(required=True, choices=get_imt_choices,
                   label='Intensity Measure Type(s)')

    def clean(self):
        """Run validation where we must validate selected gsim(s) based on
        selected intensity measure type
        """
        cleaned_data = super().clean()
        if 'gsim' in cleaned_data and 'imt' in cleaned_data:
            # both gsim and imt have "survived" the validation and are valid
            # check their relative validity:
            self.validate_gsim_and_imt(cleaned_data['gsim'], cleaned_data['imt'])
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
            self.add_error('gsim', err_gsim)
            if 'imt' in self.errors:
                self.errors.pop('imt', None)
            self.add_error('imt', err_imt)

    @staticmethod
    def shared_imts(gsim_names):
        """Returns a list of IMT names shared by *all* the given GSIMs

        :param gsim_names: list of strings denoting GSIM names
        """
        if not gsim_names:
            return []

        # https://stackoverflow.com/a/8637972
        objs = models.Imt.objects
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
        objs = models.Gsim.objects
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
    def get_data_format(self):
        return self.data['data_format']

    data_format = ChoiceField(required=False, initial=DATA_FORMAT_JSON,
                              label='The format of the response data',
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
        tsep, tdec = 'csv_sep', 'csv_dec'
        # convert to symbols:
        if cleaned_data['data_format'] == self.DATA_FORMAT_CSV \
                and cleaned_data[tsep] == cleaned_data[tdec]:
            msg = gettext("'%s' must differ from '%s' in 'csv' format" %
                          (tsep, tdec))
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

    # FIXME REMOVE
    # def clean(self):
    #     GsimImtForm.clean(self)
    #     MediaTypeForm.clean(self)
    #     return self.cleaned_data

    @property
    def response_data(self) -> Union[dict, StringIO, None]:
        """Return the response data by processing the form data, or None if
        the form is invalid (`self.is_valid() == False`)
        """
        if not self.is_valid():
            return None

        # FIXME REMOVE COMMENT HERE
        # Use `self.cleaned_data` as input for `process-data`, but remove those
        # parameters (Field names) not given by the user and with no `initial`
        # (`initial` acts as a default, see `EgsimBaseForm.__init__`). E.g.
        # Django `MultiplechoiceField`s with `required=False` defaults to `[]` in
        # `cleaned_data`, and this might not be the value `process_data` expects
        # c_data = {k: v for k, v in self.cleaned_data.items() if k in self.data}
        c_data = self.cleaned_data

        obj = self.process_data(c_data) or {}
        if self.cleaned_data['data_format'] == MediaTypeForm.DATA_FORMAT_CSV:
            obj = self.to_csv_buffer(obj, c_data['csv_sep'], c_data['csv_dec'])
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


#############
# Utilities #
#############


def vectorize(value):
    """Return `value` if it is already an iterable, otherwise `[value]`.
    Note that :class:`str` and :class:`bytes` are considered scalars:
    ```
        vectorize(3) = vectorize([3]) = [3]
        vectorize('a') = vectorize(['a']) = ['a']
    ```
    """
    return [value] if isscalar(value) else value


def isscalar(value):
    """Return True if `value` is a scalar object, i.e. a :class:`str`, a
    :class:`bytes` or without the attribute '__iter__'. Example:
    ```
        isscalar(1) == isscalar('a') == True
        isscalar([1]) == isscalar(['a']) == False
    ```
    """
    return not hasattr(value, '__iter__') or isinstance(value, (str, bytes))


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