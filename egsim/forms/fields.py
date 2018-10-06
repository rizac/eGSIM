'''
Created on 16 Sep 2018

@author: riccardo
'''
import re
from fnmatch import translate
import json
import shlex
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



class ArrayField(CharField):
    '''
        Implements a django CharField which parses and validates the input expecting a
        string-formatted element (or an array of elements) in JSON or Unix shell
        (space separated variables) formats. Note that in both syntaxes leading and trailing
        square brackets are optional.
        The type of the parsed elements depends on the method `self.parse(token)`
        which by default returns `token` but might be overridden by subclasses
        (see. :class:`NArrayField`).
        As Form fields act also as validators, an object of this class can deal also with
        already parsed arrays (e.g., after inputing Yaml POST data in yaml format which would
        return an array of python objects and not their string representation).
    '''
    def __init__(self, *, min_count=None, max_count=None, min_value=None, max_value=None,
                 **kwargs):
        '''Initializes a new ArrayField
         :param min_count: numeric or None. The minimum required count of the elements
             of the parsed array. Note that `min_length` is already defined in the super-class.
             If None (the default), parsed array can have any minimum length >=0.
         :param max_count: numeric or None. The maximum required count of the elements
             of the parsed array. Note that `max_length` is already defined in the super-class.
             If None (the default), parsed array can have any maximum length >=0.
         :param min_value: object. The minimum possible value for the
             elements of the parsed array. If None (the default) do not impose any minimum
             value. If iterable, sets the minimum required value element-wise (padding with
             None or slicing in case of lengths mismatch)
         :param max_value: object. Self-explanatory. Behaves the same as `min_value`
         :param kwargs: keyword arguments forwarded to the Django super-class.
        '''
        # Parameters after “*” or “*identifier” are keyword-only parameters
        # and may only be passed used keyword arguments.
        super(ArrayField, self).__init__(**kwargs)
        self.min_count = min_count
        self.max_count = max_count
        self.min_value = min_value
        self.max_value = max_value

    def to_python(self, value):  # pylint: disable=too-many-branches, too-many-locals
        # three scenarios: iterable: take iterable
        # non iterable: parse [value]
        # string: split value into iterable
        is_vector = not isscalar(value)
        if not is_vector and isinstance(value, str):
            value = value.strip()
            is_vector = value[:1] == '['
            if is_vector != (value[-1:] == ']'):
                raise ValidationError('unbalanced brackets')
            try:
                value = json.loads(value if is_vector else "[%s]" % value)
            except Exception:  # pylint: disable=broad-except
                try:
                    value = shlex.split(value[1:-1].strip() if is_vector else value)
                except Exception:
                    raise ValidationError('Input syntax error')

        values = []
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
                is_vector = True  # force the return value to be list even if we have 1 element
                values.extend(vls)

        # check lengths:
        try:
            self.checkragne(len(values), self.min_count, self.max_count)
        except ValidationError as verr:  # just re-format exception string and raise:
            # msg should be in the form '% not in ...', remove first '%s'
            msg = verr.message[verr.message.find(' '):]
            raise ValidationError('number of elements (%d) %s' % (len(values), msg))

        # check bounds:
        minval, maxval = self.min_value, self.max_value
        minval = [minval] * len(values) if isscalar(minval) else minval
        maxval = [maxval] * len(values) if isscalar(maxval) else maxval
        for numval, mnval, mxval in zip(values, chain(minval, repeat(None)),
                                        chain(maxval, repeat(None))):
            self.checkragne(numval, mnval, mxval)

        return values[0] if (len(values) == 1 and not is_vector) else values

    @classmethod
    def parse(cls, token):  # pylint: disable=no-self-use
        '''Parses token and returns either an object or an iterable of objects.
        This method can safely raise any exception, if not ValidationError
        it will be wrapped into a suitable ValidationError'''
        return token

    @staticmethod
    def isinragne(value, minval=None, maxval=None):
        '''Returns True if the given value is in the range defined by minval and maxval
            (endpoints are included). None's in minval and maxval mean: do not check'''
        try:
            NArrayField.checkragne(value, minval, maxval)
            return True
        except ValidationError:
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
            raise ValidationError('%s not in [%s, %s]' % (str(value), str(minval), str(maxval)))
        elif toolow:
            raise ValidationError('%s < %s' % (str(value), str(minval)))
        elif toohigh:
            raise ValidationError('%s > %s' % (str(value), str(maxval)))


class NArrayField(ArrayField):
    '''ArrayField for sequences of numbers'''

    @staticmethod
    def float(val):
        '''wrapper around the built-in `float` function. Raises ValidationError in case of errors'''
        try:
            return float(val)
        except ValueError:
            raise ValidationError("Not a number: '%s'" % val)
        except TypeError:
            raise ValidationError("input must be string(s) or number(s), not '%s'" % str(val))

    @classmethod
    def parse(cls, token):
        '''Parses `token` into float.
        :param token: A python object denoting a token to be pared
        '''
        try:
            return cls.float(token)
        except ValidationError:
            if not isinstance(token, str):
                raise

        # parse semicolon as in matlab: 1:3 = [1,2,3],  1:2:3 = [1,3]
        spl = [_.strip() for _ in token.split(':')]
        if len(spl) < 2 or len(spl) > 3:
            if ':' in token:
                raise ValidationError("Expected format '<start>:<end>' or "
                                      "'<start>:<step>:<end>', found: '%s'" % token)
            else:
                raise ValidationError("Unparsable string '%s'" % token)

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


# https://docs.djangoproject.com/en/2.0/ref/forms/fields/#creating-custom-fields
class PointField(NArrayField):
    '''NArrayField which validates a 2-element iterable and returns an openquake Point'''
    def __init__(self, **kwargs):
        super(PointField, self).__init__(min_count=2, max_count=3, **kwargs)

    def clean(self, value):
        '''Converts the given value to a :class:` openquake.hazardlib.geo.point.Point` object.
        It is usually better to perform these types of conversions subclassing `clean`, as the
        latter is called at the end of the validation workflow'''
        value = NArrayField.clean(self, value)
        try:
            return Point(*value)
        except Exception as exc:
            raise ValidationError(_(str(exc)), code='invalid')


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


class GmdbField(EgsimChoiceField):
    '''EgsimChoiceField for Ground motion databases'''
    # last argument is unused
    _base_choices = zip(EGSIM.gmdb_names(), EGSIM.gmdb_names(), repeat(''))

    def map(self, value):
        '''overrides super.map in that it does not return the third argument of _base_choices
        above but the Ground motion database lazily created only on demand because
        time-consuming'''
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


class MultipleChoiceWildcardField(MultipleChoiceField):
    '''MultipleChoiceField which accepts lists of values (the default) but also a single string,
    in which case the string will be converted
    to regex and all matching elements will be returned'''

    def to_python(self, value):
        if isinstance(value, str):
            reg = MultipleChoiceWildcardField.to_regex(value)
            value = [k for k, _ in self.choices if reg.match(str(k))]
        return super(MultipleChoiceWildcardField, self).to_python(value)

    @staticmethod
    def to_regex(value):
        '''converts string (a unix shell string, see
        https://docs.python.org/3/library/fnmatch.html) to regexp
        '''
        if not value:
            return re.compile(".*")
        return re.compile(translate(value))


class GsimField(MultipleChoiceWildcardField):
    '''MultipleChoiceWildcardField with default `choices` argument, if not provided'''
    def __init__(self, **kwargs):
        kwargs.setdefault('choices', zip(EGSIM.aval_gsims(), EGSIM.aval_gsims()))
        super(GsimField, self).__init__(**kwargs)


# https://docs.djangoproject.com/en/2.0/ref/forms/fields/#creating-custom-fields
class IMTField(MultipleChoiceWildcardField):
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
        kwargs.setdefault('choices', zip(EGSIM.aval_imts(), EGSIM.aval_imts()))
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
        except Exception:  # pylint: disable=broad-except
            return False


class TrtField(MultipleChoiceWildcardField):
    '''MultipleChoiceWildcardField field which returns a tuple of Trelliplot classes
    from its clean() method (overridden)
    '''

    # remember! _choices is a super-class reserved attribute!!!
    _base_choices = {i.replace(' ', '').lower(): i for i in EGSIM.aval_trts()}

    def __init__(self, **kwargs):
        # the available choices are the OpenQuake tectnotic regions stripped with spaces
        # and with no uppercase,
        # mapped to the OpenQuake tectonic region for visualization purposes (not used for the
        # moment as this field is not rendered in django)
        kwargs.setdefault('choices', self._base_choices.items())
        super(TrtField, self).__init__(**kwargs)

    def clean(self, value):
        '''validates the value (list) allowing for standard OQ tectonic region names (with
        spaces as well as their corresponding -space-removed, lowercased versions'''
        if value is None:
            return value
        keys = [v if v in self._base_choices else v.replace(' ', '').lower() for v in value]
        super().clean(keys)
        return [self._base_choices[k] for k in keys]  # return in any case a list of OQ tr's
