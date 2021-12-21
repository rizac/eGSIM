"""eGSIM Django Fields"""

from fnmatch import translate
import re
import json
import shlex
from itertools import chain, repeat
from typing import Collection, Any, Union

import numpy as np
from openquake.hazardlib import imt
from django.core.exceptions import ValidationError

# import here all Fields used in this project to have a common namespace:
from django.forms.fields import (ChoiceField, FloatField, BooleanField,
                                 CharField, MultipleChoiceField, FileField)
from django.forms.models import ModelChoiceField


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


class ArrayField(CharField):
    """Django CharField subclass which parses and validates arrays given as
    string of text in JSON or Unix shell syntax (i.e., with space separated
    variables). An object of this class also accepts arrays given in the native
    Python type (e.g. `["a", 1]` instead of the string '["a", 1]')
    """
    def __init__(self, *, min_count=None, max_count=None,
                 min_value=None, max_value=None, **kwargs):
        """Initialize a new ArrayField

         :param min_count: numeric or None. The minimum number of elements of
            the parsed array. Raises ValueError if the array has less elements.
            None means ignore/do not check
         :param max_count: numeric or None. The maximum number of elements of
            the parsed array. See `min_count` for details
         :param min_value: object. The minimum value for the elements of the
            parsed array. None means ignore/do not check
         :param max_value: object. The maximum value for the elements of the
            parsed array. See `min_value` for details
         :param kwargs: keyword arguments forwarded to the Django super-class
        """
        # Parameters after “*” or “*identifier” are keyword-only parameters
        # and may only be passed used keyword arguments.
        super(ArrayField, self).__init__(**kwargs)
        self.min_count = min_count
        self.max_count = max_count
        self.min_value = min_value
        self.max_value = max_value

    def to_python(self, value):
        if value is None:
            return None

        tokens = self.split(value) if isinstance(value, str) else value
        is_vector = not isscalar(tokens)

        values = []
        for val in self.parse_tokens(tokens if is_vector else [tokens]):
            if isscalar(val):
                values.append(val)
            else:
                is_vector = True  # force the return value to be list
                values.extend(val)

        # check lengths:
        try:
            self.checkrange(len(values), self.min_count, self.max_count)
        except ValidationError as v_err:
            # verr message starts with len(values), reformat it:
            raise ValidationError(f'number of elements {v_err.message}')

        # check bounds:
        for val, min_v, max_v in zip(values, repeat(self.min_value),
                                     repeat(self.max_value)):
            self.checkrange(val, min_v, max_v)

        return values[0] if (len(values) == 1 and not is_vector) else values

    def split(self, value: str):
        """Split the given value (str) into tokens according to json or shlex,
        in this order (json accepts arrays without brackets)
        """
        try:
            return json.loads(value)
        except Exception:  # noqa
            try:
                return shlex.split(value.strip())
            except Exception:
                raise ValidationError('Input syntax error')

    @classmethod
    def parse_tokens(cls, tokens: Collection[str]) -> Any:
        """Parse each token in `tokens` (calling self.parse(token) and yield the
        parsed token, which can be ANY value (also lists/tuples)
        """
        for val in tokens:
            try:
                yield cls.parse(val)
            except ValidationError:
                raise
            except Exception as exc:
                raise ValidationError("%s: %s" % (str(val), str(exc)))

    @classmethod
    def parse(cls, token: str) -> Any:
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
            raise ValidationError(f'{value} not in [{minval}, {maxval}]')
        if toolow:
            raise ValidationError(f'{value} < {minval}')
        if toohigh:
            raise ValidationError(f'{value} > {maxval}')
        # if toolow and toohigh:
        #     raise ValidationError('%s not in [%s, %s]' %
        #                           (str(value), str(minval), str(maxval)))
        # if toolow:
        #     raise ValidationError('%s < %s' % (str(value), str(minval)))
        # if toohigh:
        #     raise ValidationError('%s > %s' % (str(value), str(maxval)))


class NArrayField(ArrayField):
    """ArrayField for sequences of numbers"""

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
            if not isinstance(token, str) or (':' not in token):
                raise

        # token is a str with ':' in it. Let's try to parse it as matlab range:
        tokens = [_.strip() for _ in token.split(':')]
        if len(tokens) < 2 or len(tokens) > 3:
            raise ValidationError(f"Expected format '<start>:<end>' or "
                                  f"'<start>:<step>:<end>', found: {token}")

        start = cls.float(tokens[0])
        step = 1 if len(tokens) == 2 else cls.float(tokens[1])
        stop = cls.float(tokens[-1])
        rng = np.arange(start, stop, step, dtype=float)

        # round numbers to max number of decimals input:
        decimals = cls.max_decimals(tokens)
        if decimals is not None:
            if round(rng[-1].item() + step, decimals) == round(stop, decimals):
                rng = np.append(rng, stop)

            rng = np.round(rng, decimals=decimals)

            if decimals == 0:
                rng = rng.astype(int)

        return rng.tolist()

    @staticmethod
    def float(val):
        """Wrapper around the built-in `float` function.
        Raises ValidationError in case of errors"""
        try:
            return float(val)
        except ValueError:
            raise ValidationError(f"Not a number: {val}")
        except TypeError:
            raise ValidationError(f"Expected string(s) or number(s), "
                                  f"not {val.__class__}")

    @classmethod
    def max_decimals(cls, tokens: Collection[str]):
        """Return the maximum number of decimal digits necessary and sufficient
         to represent each token string without precision loss.
         Return None if the number could not be inferred.

        :param tokens: a sequence of strings representing numbers
        """
        decimals = 0
        for token in tokens:
            _decimals = cls.decimals(token)
            if _decimals is None:
                return None
            decimals = max(decimals, _decimals)
        # return 0 as we do not care for big numbers (they are int anyway)
        return decimals

    @classmethod
    def decimals(cls, token: str) -> Union[int, None]:
        """Return the number of decimal digits necessary and sufficient
         to represent the token string as float without precision loss.
         Return None if the number could not be inferred.

        :param token: a string representing a number,  e.g. '1', '11.5', '0.8e-11'
        """
        idx_dot = token.rfind('.')
        idx_exp = token.lower().find('e')
        if idx_dot > idx_exp > -1:
            return None
        # decimal digits inferred from exponent:
        dec_exp = 0
        if idx_exp > -1:
            try:
                dec_exp = -int(token[idx_exp+1:])
            except ValueError:
                return None
            token = token[:idx_exp]
        # decimal digits after the period and until 'e' or end of string:
        dec_dot = 0
        if idx_dot > -1:
            dec_dot = len(token[idx_dot+1:])
        return max(0, dec_dot + dec_exp)


class MultipleChoiceWildcardField(MultipleChoiceField):
    """Extension of Django MultipleChoiceField:
     - Accepts lists of strings or a single string
       (which will be converted to a 1-element list)
    - Accepts wildcard in strings in order to include all matching elements
    """

    def to_python(self, value):
        """convert strings with wildcards to matching elements, and calls the
        super method with the converted value. For valid wildcard characters,
        see https://docs.python.org/3.4/library/fnmatch.html
        """
        # value might be None, string, list
        if value and isinstance(value, str):
            value = [value]  # no need to call super
        else:
            # assure that value is a list/tuple:
            value = super(MultipleChoiceWildcardField, self).to_python(value)

        have_wildcard = {_: self.has_wildcards(_) for _ in value}
        if not any(have_wildcard.values()):
            return value

        # Convert wildcard strings:
        choices = [_[0] for _ in self.choices if _[0] not in value]
        new_value = []
        for val, has_wildcard in have_wildcard.items():
            if not has_wildcard:
                new_value.append(val)
                continue
            reg = self.to_regex(val)
            new_val = [c for c in choices if reg.match(c) and c not in new_value]
            new_value += new_val

        return new_value

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


class ImtField(MultipleChoiceWildcardField):
    """Field for IMT class selection. Provides a further validation for
    SA which is provided as (or with) periods (se meth:`valid_value`)
    """

    def to_python(self, value: list):
        """Coerce value to a valid IMT string"""
        value = super().to_python(value)  # assure is a list without regexp(s)
        for i, val in enumerate(value):
            try:
                # normalize val (e.g.  '0.2' -> 'SA(0.2)'):
                _ = imt.from_string(val.strip()).string
                if val != _:
                    value[i] = _
            except KeyError as kerr:
                # raised if `val` a non-imt string, e.g. 'abc'. Provide a better
                # message than simply "abc":
                raise ValidationError(f'invalid {str(kerr)}')
            except Exception as exc:
                raise ValidationError(str(exc))  # => register error in the form
        return value

    def valid_value(self, value: str):
        """Checks that value is in the choices"""
        # if we have 'SA(...)' we must validate 'SA':
        return super().valid_value('SA' if value.startswith('SA(') else value)
