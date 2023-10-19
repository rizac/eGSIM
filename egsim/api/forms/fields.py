"""eGSIM Django Fields"""

import re
from fnmatch import translate
from itertools import chain, repeat
from typing import Collection, Any, Union, Sequence

import numpy as np
from openquake.hazardlib import imt
from django.core.exceptions import ValidationError
from django.forms.fields import Field, CharField, MultipleChoiceField

from egsim.smtk import InvalidInput
from egsim.smtk.validators import harmonize_input_gsims, harmonize_input_imts


def vectorize(value: Any) -> Sequence[Any]:
    """Return a Sequence from `value`. If `value` is already a Sequence (list, tuple),
    return it. If value is an iterable, return `list(value)`, if value is a scalar
    (including `str` and `bytes`), return `[value]`. Example
    ```
        vectorize(3) = vectorize([3]) = [3]
        vectorize('a') = vectorize(['a']) = ['a']
    ```
    """
    if isscalar(value):
        return [value]
    return value if hasattr(value, '__len__') else list(value)


def isscalar(value: Any) -> bool:
    """Return True if `value` is a scalar object, i.e. not iterable. Note that
    `str` and `bytes` are considered scalars. Example:
    ```
        isscalar(1) == isscalar('a') == True
        isscalar([1]) == isscalar(['a']) == False
    ```
    """
    return not hasattr(value, '__iter__') or isinstance(value, (str, bytes))


_split_re = re.compile(r"\s*,\s*|\s+")


def split_string(string: str) -> list[str]:
    """This function is used in all Fields accepting multiple parameters
    (NArrayField, MultipleChoiceWildcardField) to split a string using commas or
    spaces as separators.
    This is the way to provide multiple values in URL query strings and HTML
    <input> components, and it is extended also to POST request, so that
    ["a", "b"] can be also typed as "a,b", "a b", "a , b" even in YAML or JSON files

    :return: a list of chunks of the given string
    """
    _string = string.strip()
    return [] if not _string else _split_re.split(_string)


# global default error codes mapped to custom messages messages replacing Django default.
# Keys can be found in the attr. `default_error_messages` of `django.form.fields.Field`s,
# the setup of these default is performed in `egsim.api.forms.EgsimFormMeta.__new__`:
_default_error_messages = {
    "required": "This parameter is required",
    "invalid_choice": "Value not found or misspelled: %(value)s",
    "invalid_list": "Enter a list of values",
}


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
        # store now if we should try returning a scalar value (e.g. the 1st element
        # only instead of a 1-element list):
        return_scalar = isscalar(value)
        if return_scalar:
            if isinstance(value, str):  # split around commas and spaces, if possible:
                tokens = split_string(value)
                # if value contained commas or spaces (i.e., tokens == [value]), then
                # the user intended to return a vector, not a scalar:
                return_scalar = list(tokens) == [value]
            else:
                tokens = vectorize(value)
        else:
            tokens = value

        values = []
        for val in self.parse_tokens(tokens):
            if isscalar(val):
                values.append(val)
            else:
                return_scalar = False  # force the return value to be list
                values.extend(val)

        # check lengths:
        try:
            self.checkrange(len(values), self.min_count, self.max_count)
        except ValidationError as v_err:
            # verr message starts with len(values), reformat it:
            raise ValidationError(f'number of elements {v_err.message}')

        # check bounds:
        min_v, max_v = self.min_value, self.max_value
        min_v = repeat(min_v) if isscalar(min_v) else chain(min_v, repeat(None))
        max_v = repeat(max_v) if isscalar(max_v) else chain(max_v, repeat(None))
        for val, min_val, max_val in zip(values, min_v, max_v):
            self.checkrange(val, min_val, max_val)

        return values[0] if (len(values) == 1 and return_scalar) else values

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


class GsimField(MultipleChoiceField):

    def clean(self, value):
        """Custom clean, bypasses self.to_python, self.validate and self.run_validators"""
        try:
            return harmonize_input_gsims(value or [])
        except InvalidInput as err:
            raise ValidationError(
                self.error_messages["invalid_choice"],
                code="invalid_choice",
                params={"value": str(err)},
            )


class ImtField(MultipleChoiceField):

    def clean(self, value):
        """Custom clean, bypasses self.to_python, self.validate and self.run _validators"""
        try:
            return harmonize_input_imts(value or [])
        except InvalidInput as err:
            raise ValidationError(
                self.error_messages["invalid_choice"],
                code="invalid_choice",
                params={"value": str(err)},
            )


# class MultipleChoiceWildcardField(MultipleChoiceField):
#     """Extension of Django MultipleChoiceField:
#      - Accepts lists of strings or a single string. In the latter case, if the string
#        contains commas or spaces it is split around those characters and converted to
#        list, otherwise converted to a 1-element list: [string]
#      - Accepts wildcard in strings in order to include all matching elements
#     """
#     # Reminder. The central validation method of the superclass is:
#     # def clean(self, value):
#     #     value = self.to_python(value)
#     #     self.validate(value) # -> calls self.valid_value(v) for v in value
#     #     self.run_validators(value)
#     #     return value
#
#     def to_python(self, value: Union[str, Sequence[Any]]) -> list[str]:
#         """Return an unique list of elements after expanding strings with wildcards
#         to matching elements. For wildcard strings, see `fnmatch` in the Python doc
#         """
#         # copied to the super.to_python because in case of str, we split it, and in case
#         # of lists or tuples we do nothing instead of creating: [str(_) for _ in values]
#         if not value:
#             return []
#         elif isinstance(value, str):
#             # convert "a,b" "a b" "a , b" into ["a", "b"], if needed:
#             value = split_string(value)
#         elif not isinstance(value, (list, tuple)):
#             raise ValidationError(
#                 self.error_messages["invalid_list"], code="invalid_list"
#             )
#         # Now store items to return as dict keys
#         # (kind of overkill but we need fast search and to preserve insertion order):
#         new_value = {}
#         for val in value:
#             if self.has_wildcards(val):
#                 reg = self.to_regex(val)
#                 for item, _ in self.choices:
#                     if item not in new_value and reg.match(item):
#                         new_value[item] = None  # the mapped value is irrelevant
#             elif val not in new_value:
#                 new_value[val] = None  # the mapped value is irrelevant
#
#         return list(new_value.keys())
#
#     def validate(self, value: list[str]) -> None:
#         """Validate the list of values. Same as the super method, but all
#         invalid choice parameters are reported in the ValidationError"""
#         try:
#             super().validate(value)
#         except ValidationError as verr:
#             # raise an error with ALL parameters invalid, not only the first one:
#             if verr.code == 'invalid_choice':
#                 verr.params['value'] = ", ".join(v for v in value
#                                                  if not self.valid_value(v))
#             raise verr
#
#     @staticmethod
#     def has_wildcards(string: str) -> bool:
#         return '*' in string or '?' in string or ('[' in string and ']' in string)
#
#     @staticmethod
#     def to_regex(wildcard_string: str) -> re.Pattern:
#         """Convert string (a unix shell string, see
#         https://docs.python.org/3/library/fnmatch.html) to regexp. The latter
#         will match accounting for the case (ignore case off)
#         """
#         return re.compile(translate(wildcard_string))
#
#
# class ImtField(MultipleChoiceWildcardField):
#     """Field for IMT class selection. Provides a further validation for
#     SA which is provided as (or with) periods (se meth:`valid_value`)
#     """
#     default_error_messages = {
#         "invalid_sa_period": "Missing or invalid period: %(value)s"
#     }
#
#     def to_python(self, value: Union[str, Sequence[Any]]) -> list[str]:
#         """Coerce value to a valid IMT string. Also, raise ValidationErrors from
#         here, thus skipping self.validate() that would be called later and is usually
#         responsible for that"""
#         value = super().to_python(value)  # assure is a list without regexp(s)
#         # Now normalize the IMTs. Store each normalized IMT ina dict key in order to
#         # avoid duplicates whilst preserving order (Python sets don't preserve it):
#         new_val = {}
#         for val in value:
#             try:
#                 # Try to normalize the IMT (e.g. '0.2' -> 'SA(0.2)'):
#                 new_val[self.normalize_imt(val)] = None
#             except (KeyError, ValueError):
#                 # val is invalid, skip (we will handle the error in `self.validate`)
#                 new_val[val] = None
#         return list(new_val.keys())
#
#     def validate(self, value: list[str]) -> None:
#         invalid_choices = []
#         invalid_sa_period = []
#         for val in value:
#             try:
#                 # is IMT well written?:
#                 self.normalize_imt(val)  # noqa
#                 # is IMT supported by the program?
#                 if not self.valid_value(val):
#                     raise KeyError()  # fallback below
#             except KeyError:
#                 # `val` is invalid in OpenQuake, or not implemented in eGSIM (see above)
#                 invalid_choices.append(val)
#             except ValueError:
#                 # val not a valid float (e.g. '0.t') or given as 'SA' (without period):
#                 invalid_sa_period.append(val)
#         validation_errors = []
#         if invalid_choices:
#             validation_errors.append(ValidationError(
#                 self.error_messages["invalid_choice"],
#                 code="invalid_choice",
#                 params={"value": ", ".join(invalid_choices)},
#             ))
#         if invalid_sa_period:
#             validation_errors.append(ValidationError(
#                 self.error_messages["invalid_sa_period"],
#                 code="invalid_sa_period",
#                 params={"value": ", ".join(invalid_sa_period)},
#             ))
#         if validation_errors:
#             raise ValidationError(validation_errors)
#
#     @staticmethod
#     def normalize_imt(imt_string) -> str:
#         """Checks and return a normalized version of the given imt as string,
#         e.g. '0.1' -> 'SA(0.1)'. Raise KeyError (imt not implemented) or
#         ValueError (SA period missing or invalid)"""
#         return imt.from_string(imt_string.strip()).string  # noqa
#
#     def valid_value(self, value):
#         return super().valid_value('SA' if value.startswith('SA(') else value)


def get_field_docstring(field: Field, remove_html_tags=False):
    """Return a docstring from the given Form field `label` and `help_text`
    attributes. The returned string will be a one-line (new newlines) string
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
