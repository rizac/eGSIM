'''
Created on 16 Sep 2018

@author: riccardo
'''
import re
from itertools import chain, repeat

import numpy as np

from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from django.forms.fields import CharField, MultipleChoiceField, ChoiceField

from openquake.hazardlib import imt
from openquake.hazardlib.geo import Point
from smtk.trellis.trellis_plots import DistanceIMTTrellis, DistanceSigmaIMTTrellis, \
    MagnitudeIMTTrellis, MagnitudeSigmaIMTTrellis, MagnitudeDistanceSpectraTrellis, \
    MagnitudeDistanceSpectraSigmaTrellis
from smtk.residuals.residual_plots import residuals_density_distribution, residuals_with_depth,\
    residuals_with_distance, residuals_with_magnitude, residuals_with_vs30, likelihood

from egsim.core.utils import vectorize, EGSIM, isscalar


class NArrayField(CharField):
    '''CharField for sequences of numbers. It allwos sequences typed with optional brakets,
    commas or spaces as number separators, and the semicolon notation (as in matlab) to
    indicate a range'''
    def __init__(self, *, min_arr_len=None, max_arr_len=None, min_value=None, max_value=None,
                 **kwargs):
        '''
        Implements a numeric array django Form field.
        The `clean()` method converts input values into a numeric scalar or list, and returns it.
        The input can be a numeric scalar, an iterable of numbers, or a numeric parsable string.
        Input strings representing arrays can be given in json/python notation, with spaces also
        recognized as element separator, optional square brackets, and the matlab notation with
        semicolon to indicate a numeric range (`start:stop` or `start:step:stop`) which will be
        converted to the corresponding numeric array

        Example: ".5 ,6.2 77 0:2:3" will result in [0.5, 6.2, 77 0 2] )

         :param min_arr_len: numeric or None. The minimum required length of the parsed array.
             If None (the default), skips this check
         :param max_arr_len: numeric or None. The maximum required length of the parsed array.
             If None (the default), skips this check
         :param min_value: numeric, None or numeric array. If None (the default) skips this check.
             If numeric, it sets the minimum required value for all elements of the parsed array.
             If numeric array, sets the minimum required value for each parsed element: if the
             length is lower than the parsed elements length, it will be padded with None
             (skip check on remaining elements)
         :param max_value: numeric, None or numeric array. Same as `min_value`, but it controls
             the maximum possible value of the parsed elements
         :param kwargs: keyword arguments forwarded to the super-class.
        '''
        # Parameters after “*” or “*identifier” are keyword-only parameters
        # and may only be passed used keyword arguments.
        super(NArrayField, self).__init__(**kwargs)
        self.na_minlen = min_arr_len
        self.na_maxlen = max_arr_len
        self.min_value = min_value
        self.max_value = max_value

    def serialize(self, value, parsecolon=False):
        '''Serialises 'value' into a json- or YAML- compatible value. By default,
        it calls self.parsenarray(value, self.na_minlen, self.na_maxlen, self.min_value,
                                    self.max_value)
        This method allows to return a json or yaml compatible type which is basically
        the same as `self.clean()`, unless the latter is overridden in order to
        return more complex and non-dumpable objects.
        Moreover, note that by default if `value` or any of its elements (if `value`
        is iterable) contain the colon, ':', then value is returned as it is

        :param parsecolon: when False (the default) if `value` is a string or an iterable of
        strings, and any string contains the colon ':', then value is not processed and returned
        as it is. This avoids floating point errors and potentially long numeric arrays to be
        written to json or yaml files. When called by `self.clean`, this argument is True, as
        we do want to parse colons into range numeric arrays

        raises: ValidationError
        '''
        has_semicolon = False
        if not parsecolon:
            values = vectorize(value)
            has_semicolon = any(isinstance(v, str) and ':' in v for v in values)
        # run in any case the validation process in order to raise if an error is encountered:
        parsed_value = super(NArrayField, self).clean(value)
        try:
            parsed_value = self.parsenarray(parsed_value, self.na_minlen, self.na_maxlen,
                                            self.min_value, self.max_value)
            return value if has_semicolon else parsed_value
        except (ValueError, TypeError) as exc:
            raise ValidationError(_(str(exc)), code='invalid')

    def clean(self, value):
        """Return a number or a list of numbers depending on `value`"""
        return self.serialize(value, parsecolon=True)

    @classmethod
    def parsenarray(cls, obj, minlen=None, maxlen=None,  # pylint: disable=too-many-arguments
                    minval=None, maxval=None):
        '''parses ``obj`` into a N-element list of floats, returning that
            list.

        :pram obj: a number, a string, or an iterable of numbers or strings. By strings we intend
        any string parsable to float. Examples: 1.1, '1.1', [1,2,3], numpyarray([1,2,3]), "[1,2,3]",
        "[1 , 2 , 3]" (spaces around commas ignored) "[1 2 3]" (spaces allowed as number separator).
        All leading and trailing brakets in strings are optional (e.g. "1 2 3" eauals "[1,2,3]")

        See :ref:class:`NArrayField` init method for details
        :raises: ValueError or TypeError
        '''

        isstr = isinstance(obj, str)
        iterable = None if isscalar(obj) else obj

        if iterable is None:
            try:
                return cls.float(obj)
            except ValueError:
                pass
            iterable = cls.split(obj)

        values = []
        for val in iterable:
            if not isstr or ':' not in val:
                values.append(cls.float(val))
            else:
                values += cls.str2nprange(val)

        # check lengths:
        try:
            cls.checkragne(len(values), minlen, maxlen)
        except ValueError as verr:  # just re-format exception string and raise:
            raise ValueError('number of elements (%d)' %
                             (len(values) + str(verr)[str(verr).find(' '):]))

        # check bounds:
        minval = [] if minval is None else vectorize(minval)
        maxval = [] if maxval is None else vectorize(maxval)
        for numval, mnval, mxval in zip(values, chain(minval or [], repeat(None)),
                                        chain(maxval or [], repeat(None))):

            cls.checkragne(numval, mnval, mxval)

        return values

    @staticmethod
    def float(val):
        '''wrapper around the built-in `float` function: if TypeError is raised,
        provides a meaningful message in the exception'''
        try:
            return float(val)
        except ValueError:
            raise ValueError("Not a number: '%s'" % val)
        except TypeError:
            raise TypeError("input must be string(s) or number(s), not '%s'" % str(val))

    @staticmethod
    def split(string, ignore_colon=False):
        '''parses strings and splits it, returning the resulting list of strings.
        Recognizes as separators commas and spaces not preceded or followed by semicolons.
        Leading and trailing square brackets are optional'''
        string = string.strip()

        if not string:
            return []

        if string[0] in ('[', '('):
            if not string[-1] == {'[': ']', '(': ')'}[string[0]]:
                raise TypeError('unbalanced brackets')
            string = string[1:-1].strip()

        reg_str = "(?:\\s*,\\s*|\\s+)" if ignore_colon else "(?:\\s*,\\s*|(?<!:)\\s+(?!:))"
        return re.split(reg_str, string)

    @classmethod
    def str2nprange(cls, string):
        '''Converts the given string to a numpy range and returns the resulting list.
        A range is a sequence of equally distant numbers.
        Semicolons are treated as element separators. The given string must be in the format:
        `<start>:<stop>`
        `<start>:<step>:<stop>`
        '''
        # parse semicolon as in matlab: 1:3 = [1,2,3],  1:2:3 = [1,3]
        spl = [_.strip() for _ in string.split(':')]
        if len(spl) < 2 or len(spl) > 3:
            raise ValueError("Expected format '<start>:<end>' or "
                             "'<start>:<step>:<end>', found: '%s'" % string)
        start, step, stop = \
            cls.float(spl[0]), 1 if len(spl) == 2 else cls.float(spl[1]), cls.float(spl[-1])
        decimals = cls.get_decimals(*spl)

        arange = np.arange(start, stop, step, dtype=float)
        if decimals is not None:
            if round(arange[-1].item()+step, decimals) == round(stop, decimals):
                arange = np.append(arange, stop)

            arange = np.round(arange, decimals=decimals)
            if decimals == 0:
                arange = arange.astype(int)
        return arange.tolist()

    @classmethod
    def get_decimals(cls, *strings):
        '''parses each string and returns the maximum number of decimals
        :param strings: a sequence of strings. Note that they do not need to be parsable
        as floats, this method searches for the dot and the letter 'E' (ignoring case)
        '''
        decimals = 0
        try:
            for string in strings:
                idx_dec = string.find('.')
                idx_exp = string.lower().find('e')
                if idx_dec > -1 and idx_exp > -1 and idx_exp < idx_dec:
                    raise ValueError()  # stop parsing
                dec1 = 0 if idx_dec < 0 else \
                    len(string[idx_dec+1: None if idx_exp < 0 else idx_exp])
                dec2 = 0 if idx_exp < 0 else -int(string[idx_exp+1:])
                decimals = max([decimals, dec1, dec2])
            return decimals  # 0 as we do not care for big numbers (they are int anyway)
        except ValueError:
            return None

    @staticmethod
    def isinragne(value, minval=None, maxval=None):
        '''Returns True if the given value is in the range defined by minval and maxval
            (endpoints are included). None's in minval and maxval mean: do not check'''
        try:
            NArrayField.checkragne(value, minval, maxval)
            return True
        except ValueError:
            return False

    @staticmethod
    def checkragne(value, minval=None, maxval=None):
        '''checks that the given value is in the range defined by minval and maxval
            (endpoints are included). None's in minval and maxval mean: do not check.
            This method does not return any value but raises ValueError if value is not in the
            given range'''
        toolow = (minval is not None and value < minval)
        toohigh = (maxval is not None and value > maxval)
        if toolow and toohigh:
            raise ValueError('%s not in [%s, %s]' % (str(value), str(minval), str(maxval)))
        elif toolow:
            raise ValueError('%s < %s' % (str(value), str(minval)))
        elif toohigh:
            raise ValueError('%s > %s' % (str(value), str(maxval)))


class EgsimChoiceField(ChoiceField):
    '''Choice field which returns a user defined object mapped to the selected item

    Subclasses should implement a _base_choices CLASS attribute as list/tuple of
    3-element iterables: [(A, B, C), ... (A, B, C)], where
    the 1st element (A) is the actual value to be set on the model, the 2nd element (B) is the
    human-readable name (this is django ChoiceField default behavior) **and** the 3rd element
    is the object to be returned after validation. If a `choices` argument is passed in the
    constructor, it must have the format above (3-elements iterable) and will override the
    default `_base_choices` class attribute.
    '''
    _base_choices = []

    def __init__(self, **kwargs):  # * -> force the caller to use named arguments
        choices = kwargs.pop('choices', None)
        if choices is None:
            choices = self._base_choices
        self._mappings = {item[0]: item[2] for item in choices}
        _choices = ([item[0], item[1]] for item in choices)
        super(EgsimChoiceField, self).__init__(choices=_choices, **kwargs)

    def map(self, value):
        return self._mappings[value]

    def clean(self, value):
        # super() alone fails here. See
        # https://stackoverflow.com/a/39313448
        value = super(EgsimChoiceField, self).clean(value)  # already parsed
        return self.map(value)


# https://docs.djangoproject.com/en/2.0/ref/forms/fields/#creating-custom-fields
class IMTField(MultipleChoiceField):
    '''Field for IMT selection.
    This class overrides `to_python`, which first calls the super-method (which for
    `MultipleChoiceField`s parses the input into a list of strings), then it adds to the parsed
    list the `SA`s based on `self.sa_periods` (if truthy), which
    is a string or a list of numeric parsable strings.
    Finally, `valid_value` is overridden to ignore `self.choices` (if provided) and to
    validate each string on whether it's a valid imt or not via openquake utilities
    '''
    SA = 'SA'
    default_error_messages = {
        'sa_without_period': _("intensity measure type '%s' must "
                               "be specified with period(s)" % SA),
    }

    def __init__(self, **kwargs):
        super(IMTField, self).__init__(**kwargs)
        self.sa_periods = []  # can be string or iterable of strings
        # strings must be numeric parsable (see NArrayField)

    # this method is called first in the validation pipeline:
    def to_python(self, value):
        # call super: returns an list of strings. Excpets value to be a list or tuple:
        # if not value:
        #     return []
        # elif not isinstance(value, (list, tuple)):
        #     raise ValidationError(self.error_messages['invalid_list'], code='invalid_list')
        # return [str(val) for val in value]
        all_values = super().to_python(value)
        sastr = self.SA
        values = [v for v in all_values if v != sastr]
        if self.sa_periods:
            sa_periods = vectorize(NArrayField(required=False).clean(self.sa_periods))
            values += ['%s(%f)' % (sastr, f) for f in sa_periods]
        elif len(all_values) > len(values):
            raise ValidationError(
                self.error_messages['sa_without_period'],
                code='sa_without_period',
            )
        return values

    def valid_value(self, value):
        """
        Validate the given value, ignoring the super method which compares to the choices
        attribute
        """
        try:
            imt.from_string(value)
            return True
        except Exception as exc:
            return False


class MsrField(EgsimChoiceField):
    '''A EgsimChoiceField handling the selected Magnitude Scaling Relation object'''
    _base_choices = tuple(zip(EGSIM.aval_msr().keys(), EGSIM.aval_msr().keys(),
                              EGSIM.aval_msr().values()))


class TrellisplottypeField(EgsimChoiceField):
    '''A EgsimChoiceField returning the selected `BaseTrellis` class for computing the
        Trellis plots'''
    _base_choices = (
        ('d', 'IMT vs. Distance', DistanceIMTTrellis),
        ('m', 'IMT vs. Magnitude', MagnitudeIMTTrellis),
        ('s', 'Magnitude-Distance Spectra', MagnitudeDistanceSpectraTrellis),
        ('ds', 'IMT vs. Distance (st.dev)', DistanceSigmaIMTTrellis),
        ('ms', 'IMT vs. Magnitude  (st.dev)', MagnitudeSigmaIMTTrellis),
        ('ss', 'Magnitude-Distance Spectra  (st.dev)', MagnitudeDistanceSpectraSigmaTrellis)
    )


# https://docs.djangoproject.com/en/2.0/ref/forms/fields/#creating-custom-fields
class PointField(NArrayField):
    def __init__(self, **kwargs):
        super(PointField, self).__init__(min_arr_len=2, max_arr_len=3, **kwargs)

    def clean(self, value):
        '''Converts the given value to a :class:` openquake.hazardlib.geo.point.Point` object.
        It is usually better to perform these types of conversions subclassing `clean`, as the
        latter is called at the end of the validation workflow'''
        value = NArrayField.clean(self, value)
        try:
            return Point(*value)
        except Exception as exc:
            raise ValidationError(_(str(exc)), code='invalid')

class TrtField(MultipleChoiceField):
    '''Choice field which returns a tuple of Trelliplot classes from its clean()
    method (overridden'''

    # remember! _choices is a super-class reserved attribute!!!
    _base_choices = {i.replace(' ', '').lower(): i for i in EGSIM.aval_trts()}

    def __init__(self, **kwargs):
        # the available choices are the OpenQuake tectnotic regions stripped with spaces
        # and with no uppercase,
        # mapped to the OpenQuake tectonic region for visualization purposes (not used for the
        # moment as this field is not rendered in django)
        choices = zip(self._base_choices.keys(), self._base_choices.values())
        super(TrtField, self).__init__(choices=choices, **kwargs)

    def clean(self, value):
        '''validates the value (list) allowing for standard OQ tectonic region names (with
        spaces as well as their corresponding -space-removed, lowercased versions'''
        if value is None:
            return value
        keys = [v if v in self._base_choices else v.replace(' ', '').lower() for v in value]
        super().clean(keys)
        return [self._base_choices[k] for k in keys]  # return in any case a list of OQ tr's


class GmdbField(EgsimChoiceField):
    # last argument is unused
    _base_choices = zip(EGSIM.gmdb_names(), EGSIM.gmdb_names(), repeat(''))

    def map(self, value):
        '''overrides super.map in that it does not return the third argument of _base_choices
        above but the Ground motion database corresponding to the key 'value' (first arg of
        any argument of _base_choices above). this is doen because a Ground motion database
        is lazily created otherwise initializing this class would take forever'''
        return EGSIM.gmdb(value)



class GmdbSelectionField(EgsimChoiceField):
    '''Implements the ***FILTER*** (smtk code calls it 'selection') field on a Ground motion
    database'''
    _base_choices = zip(EGSIM.gmdb_selections(), EGSIM.gmdb_selections(),
                        EGSIM.gmdb_selections())


class ResidualplottypeField(EgsimChoiceField):
    '''An EgsimChoiceField which returns the selected function to compute residual plots'''
    _base_choices = (
        ('ddist', 'Residuals density distribution', residuals_density_distribution),
        ('mag', 'Residuals vs. Magnitude', residuals_with_magnitude),
        ('dist', 'Residuals vs. Distance', residuals_with_distance),
        ('vs30', 'Residuals vs. Vs30', residuals_with_vs30),
        ('depth', 'Residuals vs. Depth', residuals_with_depth),
        ('lh', 'Likelihood', likelihood)
    )
