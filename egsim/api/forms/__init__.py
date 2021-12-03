from fnmatch import translate
from typing import Union, Iterable
import re
import json
import shlex
from itertools import chain, repeat
from io import StringIO
import csv
import yaml

import numpy as np
from django.db.models import Q  #, Exists
from openquake.hazardlib import imt
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from django.forms import Form
from django.forms.fields import (BooleanField, CharField, FloatField,
                                 ChoiceField, CallableChoiceIterator,
                                 MultipleChoiceField, TypedChoiceField)

from .. import models

##########
# Fields #
##########


class DictChoiceField(ChoiceField):
    """ChoiceField where the choices are supplied via a class attribute
    `_base_choices` (`dict`): the dict keys are both used as form and HTML-displayed
    values, the dict values are the objects returned by `clean`
    """
    _base_choices = {}

    def __init__(self, **kwargs):
        kwargs.setdefault('choices', ((_, _) for _ in self._base_choices))
        super(DictChoiceField, self).__init__(**kwargs)

    def clean(self, value):
        """Convert the given value (string) into the OpenQuake instance
        and return the latter"""
        value = super(DictChoiceField, self).clean(value)
        return self._base_choices[value]


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
    def parse(cls, token):  # pylint: disable=no-self-use
        """Parse token and return either an object or an iterable of objects.
        This method can safely raise any exception, if not ValidationError
        it will be wrapped into a suitable ValidationError
        """
        return token

    @staticmethod
    def checkrange(value, minval=None, maxval=None):
        """Check that the given value is in the range defined by minval and
        maxval (endpoints are included). None in minval and maxval mean:
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


def get_gsim_choices(): # https://stackoverflow.com/a/57809521
    return [(_, _) for _ in models.Gsim.objects.values_list('name', flat=True)]


class GsimField(MultipleChoiceWildcardField):
    """MultipleChoiceWildcardField with default `choices` argument,
    if not provided"""

    def __init__(self, **kwargs):
        kwargs.setdefault('choices', get_gsim_choices)
        kwargs.setdefault('label', 'Ground Shaking Intensity Model(s)')
        super(GsimField, self).__init__(**kwargs)


def get_imt_choices(): # https://stackoverflow.com/a/57809521
    return [(_, _) for _ in models.Imt.objects.values_list('name', flat=True)]


class BaseImtField(MultipleChoiceWildcardField):
    """Base class for the IMT selection Form Field"""
    SA = 'SA'
    default_error_messages = {
        'sa_with_period': _("%s must be specified without period(s)" % SA),
        'sa_without_period': _("%s must be specified with period(s)" % SA),
        'invalid_sa_period': _("invalid " + SA + " period in: %(value)s"),
        'invalid_sa_periods': _("error while parsing %s period(s)" % SA)
    }

    def __init__(self, **kwargs):
        kwargs.setdefault('choices', get_imt_choices)
        kwargs.setdefault('label', 'Intensity Measure Type(s)')
        super(BaseImtField, self).__init__(**kwargs)


class ImtclassField(BaseImtField):
    """Field for IMT class selection. Inherits from `BaseImtField` (thus
    `MultipleChoiceWildcardField`): Imts should be provided as
    class names (strings) with no arguments.
    """
    def __init__(self, **kwargs):
        kwargs.setdefault('label', 'Intensity Measure Type(s)')
        super(ImtclassField, self).__init__(**kwargs)

    def valid_value(self, value):
        """Validate the given value, simply issues a more explicit warning
        message if 'SA' is provided with periods
        """
        valid = super(ImtclassField, self).valid_value(value)
        if not valid and value.startswith('%s(' % self.SA):  # not in the list
            # It is perfectly fine to raise ValidationError from here, as
            # this allows us to customize the message in case of 'SA':
            raise ValidationError(
                self.error_messages['sa_with_period'],
                code='sa_with_period',
            )

        return valid


# https://docs.djangoproject.com/en/2.0/ref/forms/fields/#creating-custom-fields
class ImtField(BaseImtField):
    """Field for IMT class selection. Inherits from `BaseImtField` (thus
    `MultipleChoiceWildcardField`): Imts should be provided as class names
    (str) with arguments, if needed. This class has also the property
    `sa_periods_str` that can be set with the string value of SA periods
    provided separately
    """
    @property
    def sa_periods_str(self):
        """Sets the SA periods as string. The periods must be formatted
        according to a `NArrayField` input (basically, shlex or json
        compatible). If provided, the `to_python` method will merge all
        provided IMTs with all string chunks `SA(P)` built from the periods
        chunks parsed from this string"""
        return getattr(self, '_sa_periods_str', '')

    @sa_periods_str.setter
    def sa_periods_str(self, value):
        setattr(self, '_sa_periods_str', value)

    def valid_value(self, value):
        """Validate the given *single* value (i.e., an element of the passed
        imt list), ignoring the super method which compares
        to the choices attribute.
        Remember that this method is called from within `self.clean` which in
        turns calls first `self.to_python` and then `self.validate`. The latter
        calls `self.valid_value` on each element of the input IMT list
        """
        if value == self.SA:
            # It is perfectly fine to raise ValidationError from here, as
            # this allows us to customize the message in case of 'SA':
            raise ValidationError(
                self.error_messages['sa_without_period'],
                code='sa_without_period',
            )
        valid = super(ImtField, self).valid_value(value)
        if not valid:
            try:
                imt.from_string(value)
                valid = True
            except Exception:  # noqa
                if value.startswith('%s(' % self.SA):
                    raise ValidationError(
                        self.error_messages['invalid_sa_period'],
                        code='invalid_sa_period',
                        params={'value': value},
                    )

        return valid

    def to_python(self, value):
        """Converts the given input value to a Python list of IMT strings
        Remember that this method is called from within `self.clean` which in
        turns calls first `self.to_python` and then `self.validate`. The latter
        calls `self.valid_value` on each element of the input IMT list
        """
        # convert strings with wildcards to matching elements
        # (see MultipleChoiceWildcardField):
        imts = ImtclassField.to_python(self, value)
        # combine with separate SA periods, if provided
        periods_str = self.sa_periods_str
        if periods_str:
            try:
                saindex = imts.index(self.SA)
            except ValueError:
                saindex = len(imts)

            try:
                periods = \
                    vectorize(NArrayField(required=False).clean(periods_str))
                ret = [_ for _ in imts if _ != self.SA]
                sa_str = '{}(%s)'.format(self.SA)
                sa_periods = [sa_str % _ for _ in periods]
                imts = ret[:saindex] + sa_periods + ret[saindex:]
            except Exception as _exc:
                raise ValidationError(
                    self.error_messages['invalid_sa_period'],
                    code='invalid_sa_period',
                    params={'value': periods_str},
                )

        return imts

    def get_imt_classnames(self, value):
        """Returns a set of strings denoting the IMT class names in `value`
        uses `self.sa_periods_str` to infer if SA is defined and should be
        returned regardless of whether it is in `value` (list of IMT strings)
        """
        # convert strings with wildcards to matching elements
        # (see MultipleChoiceWildcardField):
        imts = ImtclassField.to_python(self, value)
        ret = set()
        # check if SA is provided, and in case remove all occurrences of
        # self.SA:
        if self.sa_periods_str or any(_.startswith(self.SA) for _ in imts):
            imts = [_ for _ in imts if not _.startswith(self.SA)]
            ret = {self.SA}
        for imt_ in imts:
            try:
                ret.add(imt.from_string(imt_).__class__.__name__)
            except Exception:  # noqa
                pass
        return ret


class TextSepField(DictChoiceField):
    """A ChoiceField handling the text separators in the text response"""
    _base_choices = dict([('comma', ','), ('semicolon', ';'),
                          ('space', ' '), ('tab', '\t')])


class TextDecField(DictChoiceField):
    """A ChoiceField handling the text decimal in the text response"""
    _base_choices = dict([('period', '.'), ('comma', ',')])


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

    # Field names (str) included in the list below: 1. will be hidden from the
    # doc as they should not be exposed in the API, 2. will not returned by
    # `self.dump` (which converts this form to json or YAML object). To merge
    # with a parent class:
    # __hidden_fieldnames__ = [*ParentForm1.__hidden_fieldnames__, '<field>', ...]
    __hidden_fieldnames__ = []

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

        # if repl_dict:  FIXME: REMOVE BLOCK COMMENT
        #     for key in list(self.data.keys()):
        #         repl_key = repl_dict.get(key, None)
        #         if repl_key is not None:
        #             self.data[repl_key] = self.data.pop(key)

        # Make fields initial value the default when missing.
        # From https://stackoverflow.com/a/20309754 and other posts therein:
        # initial isn't really meant to be used to set default values for form
        # fields. Instead, it's really more a placeholder utility when
        # displaying forms to the user, and won't work well if the field isn't
        # required (see also the class method is_optional):
        for name in self.fields:
            if not self[name].html_name in self.data and \
                    self.fields[name].initial is not None:
                self.data[name] = self.fields[name].initial

        # Custom attributes for js libraries (e.,g. bootstrap, angular...)?
        # All solutions (widget_tweaks, django-angular) are too much overhead
        # in our simple scenario. This is the best solution but not that
        # after refactoring it is no-op:
        self.customize_widget_attrs()

    def clean(self):
        """Call `super.clean()`, removes from `cleaned_data` fields that were
        not provided as input and had no default given, and returns it
        """
        cleaned_data = super().clean()
        # `cleaned_data` is a `dict[str, Any]`: each key is the name of a Field
        # implemented in this class (`self.declared_fields`) mapped to its value
        # which is validated and parsed from the user input data (`self.data`).
        # What about Fields not given by the user?
        # 1. Those with an initial/default value explicitly set, were added to
        #    `self.data` in `__init__` (see above)
        # 2. Those without an initial/default value, might be initialized with
        #    a hard coded default, usually "falsy" before validation (e.g. [] in
        #    `MultipleChoiceField.to_python`). If the validation does not raise
        #    (e.g., the field is not required, see `MultipleChoiceField.validate`)
        #    we might have in `cleaned_data` field values not input by the user
        #    and with an "unknown" default (i.e. not explicitly provided)
        # Consequently, optional Fields without an initial/default value and
        # not provided as input (i.e., not in `self.data`) are removed here
        # below from `cleaned_data`:
        for key in list(_ for _ in cleaned_data if _ not in self.data):
            cleaned_data.pop(key)

        return cleaned_data

    def customize_widget_attrs(self):  # pylint: disable=no-self-use
        """Customize the widget attributes. This method is no-op and might be
        overwritten in subclasses. Check however `self.to_rendering_dict`
        which is currently the method to be used in order to inject data in
        the frontend"""
        # this method is no-op, as we delegate the view (frontend)
        # to set the custom attributes. Example in case subclassed:
        #
        # atts = {'class': 'form-control'}  # for bootstrap
        # for name, field in self.fields.items():  # @UnusedVariable
        #     if not isinstance(field.widget,
        #                       (CheckboxInput, CheckboxSelectMultiple,
        #                        RadioSelect)) and not field.widget.is_hidden:
        #         field.widget.attrs.update(atts)
        return

    def dump(self, stream=None, syntax='yaml'):
        """Serialize this Form instance into a YAML or JSON stream.
        **The form needs to be already validated via e.g. `form.is_valid()`**.
        Hidden fields in `self.__hidden_fieldnames__` are not returned.

        The result collects the fields of `self.data`, i.e., the unprocessed
        input, with one exception: if this form subclasses
        :class:`GsimImtForm`, as 'sa_period' is hidden,
        the value mapped to 'imt' will be `self.cleaned_data['imt']` and not
        `self.data['imt']`.

        :param stream: A file-like object **for text I/O** (e.g. `StringIO`),
           or None.
        :param syntax: string either json or yaml. Default: yaml

        :return: if the passed `stream` argument is None, returns the produced
            string. If the passed `stream` argument is a file-like object,
            this method writes to `stream` and returns None
        """
        if syntax not in ('yaml', 'json'):
            raise ValueError("invalid `syntax` argument in `dump`: '%s' "
                             "not in ('json', 'yam')" % syntax)

        hidden_fn = set(self.__hidden_fieldnames__)
        cleaned_data = {}
        for key, val in self.data.items():
            if key in hidden_fn:
                continue
            # Omit unchanged optional parameters. This is not only to make
            # the dumped string more readable and light size, but to avoid
            # parameters which defaults to None (e.g. z1pt0 in
            # TrellisForm): if they were written here (e.g. `z1pt0: None`) then
            # a routine converting the returned JSON/YAML to a query string
            # would wrtie "...z1pt0=null...", which might be interpreted as
            # the string "null"
            if self.is_optional(key) and val == self.fields[key].initial:
                continue
            # provide tha value given as input, not the value processed
            # by `self.clean`, which might be not JSON or YAML serializable,
            # with one exception: imt in GsimImtForm, becasue we might have
            # provided the parameter `sa_periods` and thus the processed
            # imt in `cleaned_data` is the value to return:
            cleaned_data[key] = self.cleaned_data[key] \
                if key == 'imt' and isinstance(self, GsimImtForm) else val

        if syntax == 'json':
            return self._dump_json(stream, cleaned_data)

        return self._dump_yaml(stream, cleaned_data)

    def _dump_json(self, stream, cleaned_data):  # pylint: disable=no-self-use
        """Serialize to JSON. See `self.dump`"""
        # compatibility with yaml dump if stream is None:
        if stream is None:
            return json.dumps(cleaned_data, indent=4,
                              separators=(',', ': '), sort_keys=True)
        json.dump(cleaned_data, stream, indent=4, separators=(',', ': '),
                  sort_keys=True)
        return None

    def _dump_yaml(self, stream, cleaned_data):
        """Serialize to YAML. See `self.dump`"""

        class MyDumper(yaml.SafeDumper):  # noqa
            """Force indentation of lists"""
            # For info see: https://stackoverflow.com/a/39681672
            def increase_indent(self, flow=False, indentless=False):
                return super(MyDumper, self).increase_indent(flow, False)

        # regexp to replace html entities with their content, i.e.:
        # <a href='#'>bla</a> -> bla
        # V<sub>s30</sub> -> Vs30
        # ... and so on ...
        html_tags_re = re.compile('<(\\w+)(?: [^>]+|)>(.*?)<\\/\\1>')

        # inject comments in yaml by using the field label and its help:
        stringio = StringIO() if stream is None else stream
        fields = self.to_rendering_dict(ignore_callable_choices=False)
        for name, value in cleaned_data.items():
            field = fields[name]
            label = (field['label'] or '') + \
                ('' if not field['help'] else ' (%s)' % field['help'])
            if label:
                # replace html characters with their content
                # (or empty str if no content):
                label = html_tags_re.sub(r'\2', label)
                # replace newlines for safety:
                label = '# %s\n' % (label.replace('\n', ' ').
                                    replace('\r', ' '))
                stringio.write(label)
            yaml.dump({name: value}, stream=stringio, Dumper=MyDumper,
                      default_flow_style=False)
            stringio.write('\n')
        # compatibility with yaml dump if stream is None:
        if stream is None:
            ret = stringio.getvalue()
            stringio.close()
            return ret
        return None

    @classmethod
    def is_optional(cls, field):
        """Return True if the given Field is optional, i.e. if it is not
        required or its initial value is given (i.e., not None. A field initial
        value acts as default value when missing)

        :param field: a Field object or a string denoting the name of one of
            this Form's fields
        """
        if isinstance(field, str):
            field = cls.declared_fields[field]
        return not field.required or field.initial is not None

    def to_rendering_dict(self, ignore_callable_choices=True) -> dict:
        """Convert this form to a Python dict for rendering the field as input
        in the frontend, allowing it to be injected into frontend libraries
        like VueJS (the currently used library) or AngularJS: each
        Field name is mapped to a dict of keys such as 'val' (the value),
        'help' (the help text), 'label' (the label text), 'err':
        (the error text), 'attrs' (a dict of HTML element attributes),
        'choices' (the list of available choices, see argument
        `ignore_callable_choices`).

        :param ignore_callable_choices: handles the 'choices' for fields
            defining it as CallableChoiceIterator: if True (the default) the
            function is not evluated and the choices are simply set to [].
            If False, the choices function will be evaluated.
            Use True when the choices list is too big and you do not need
            this additional overhead (see e.g. in `view`.main`, when we create
            the start HTML).
        """
        # import here stuff used only in this method:
        from collections import defaultdict

        hidden_fn = set(self.__hidden_fieldnames__)
        formdata = {}
        aliases = {}
        self.fieldname_aliases(aliases)
        optional_names = defaultdict(list)
        for key, val in aliases.items():
            optional_names[val].append(key)
        for name, field in self.declared_fields.items():  # pylint: disable=no-member
            # little spec needed before proceeding:
            # `self.declared_fields` and `self.base_fields` are the same thing
            # (see django.forms.forms.DeclarativeFieldsMetaclass) and are
            # declared at CLASS level: modifying them applies changes to all
            # instances, thus avoid. Conversely, `self.fields[name]` is where
            # specific instance-level changes have to be made:
            # https://docs.djangoproject.com/en/2.2/ref/forms/api/#accessing-the-fields-from-the-form
            # Finally, `self[name]` creates a `BoundField` from
            # `self.fields[name]` i.e. "a Field plus data" (e.g., its initial
            # value, if given. See `__init__`). `BoundField`s is what we want
            # to use here
            boundfield = self[name]
            val = boundfield.value()
            widget = boundfield.field.widget
            attrs = boundfield.build_widget_attrs({}, widget)
            widgetdata = widget.get_context(name, val, attrs)['widget']
            attrs = dict(widgetdata.pop('attrs', {}))
            if 'type' in widgetdata:
                attrs['type'] = widgetdata.pop('type')
            if 'required' in widgetdata:
                attrs['required'] = widgetdata.pop('required')
            if 'id' not in attrs:
                attrs['id'] = boundfield.auto_id
            attrs['name'] = widgetdata.pop('name')
            # coerce val to [] in case val falsy and multichoice:
            if isinstance(field, MultipleChoiceField) and not val:
                val = []
            # type description:
            fielddata = {  # noqa
                'name': attrs['name'],
                'opt_names': optional_names.get(name, []),
                'is_optional': self.is_optional(name),
                'help': boundfield.help_text,
                'label': boundfield.label,
                'attrs': attrs,
                'err': '',
                'is_hidden': widgetdata.pop('is_hidden',
                                            False) or name in hidden_fn,
                'val': val,
                'initial': field.initial,
                'typedesc': EgsimBaseForm._type_description(field,
                                                            attrs.get('min', None),
                                                            attrs.get('max', None))
            }
            fielddata['choices'] = getattr(field, 'choices', [])
            if isinstance(fielddata['choices'], CallableChoiceIterator):
                if ignore_callable_choices:
                    fielddata['choices'] = []
                else:
                    fielddata['choices'] = list(fielddata['choices'])
            formdata[name] = fielddata
        return formdata

    @staticmethod
    def _type_description(field, minval=None, maxval=None):
        """Return a human readable type description for the given field"""
        # type description:
        typedesc = 'UNKNOWN_TYPE'
        if isinstance(field, NArrayField):
            if field.min_count is not None and field.min_count > 1:
                typedesc = 'Numeric array'
            else:
                typedesc = 'Numeric or numeric array'
        elif isinstance(field, MultipleChoiceWildcardField):
            typedesc = 'String or string array'
        elif isinstance(field, MultipleChoiceField):
            typedesc = 'String array'
        elif isinstance(field, (CharField, ChoiceField)):
            typedesc = 'String'
        elif isinstance(field, BooleanField):
            typedesc = 'Boolean'
        elif isinstance(field, FloatField):
            typedesc = 'Numeric'
            if minval is not None and maxval is None:
                typedesc += ' ≥ %d' % minval
            elif minval is None and maxval is not None:
                typedesc += ' ≤ %d' % maxval
            elif minval is not None and maxval is not None:
                typedesc += ' in [%d, %d]' % (minval, maxval)

        return typedesc

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

    __hidden_fieldnames__ = ['sa_period']

    gsim = GsimField(required=True)
    imt = ImtField(required=True)
    # sa_periods should not be exposed through the API, it is only used
    # from the frontend GUI. Thus required=False is necessary.
    # We use a CharField because in principle it should never raise: If SA
    # periods are malformed, the IMT field will hold the error in the response
    sa_period = CharField(label="SA period(s)", required=False)

    def __init__(self, *args, **kwargs):
        super(GsimImtForm, self).__init__(*args, **kwargs)
        # remove sa_periods and put them in imt field:
        self.fields['imt'].sa_periods_str = self.data.pop('sa_period', '')

    def clean(self):
        """Run validation where we must validate selected gsim(s) based on
        selected intensity measure type. For info see:
        https://docs.djangoproject.com/en/1.11/ref/forms/validation/#cleaning-and-validating-fields-that-depend-on-each-other
        """
        # UNCOMMENT THE BLOCK BELOW IF YOU WISH TO BE STRICT with unknown params
        # # check that we did not provide unknown parameters. This might not be necessary
        # # but it might help warning the user for typos in case
        # unknown_params = set(self.data) - set(self.fields)
        # if unknown_params:
        #     raise ValidationError([
        #         ValidationError(_("unknown parameter '%(param)s'"),
        #                         params={'param': p}, code='unknown')
        #         for p in unknown_params])

        super().clean()
        self.validate_gsim_and_imt()
        return self.cleaned_data

    def validate_gsim_and_imt(self):
        """Validate gsim and imt assuring that all gsims are defined for all
        supplied imts, and all imts are defined for all supplied gsim.
        This method calls self.add_error and works on self.cleaned_data, thus
        it should be called after super().clean()
        """
        # the check here is to replace potential imt errors with
        # the more relevant mismatch with the supplied gsim.
        # E.g., if the user supplied imt = 'SA(abc)' (error) and
        # a gsim='SomeGsimNotDefinedForSA', the error dict should replace
        # the SA error with 'Imt not defined for supplied Gsim':
        gsims = self.cleaned_data.get("gsim", [])
        # return the class names of the supplied Imts. Thus 'Sa(...), Sa(...)'
        # is counted once as 'SA':
        imts = self.fields['imt'].get_imt_classnames(self.data.get('imt', ''))

        if gsims and imts:
            invalid_gsims = set(gsims) - set(self.sharing_gsims(imts))

            if invalid_gsims:
                # instead of raising ValidationError, which is keyed with
                # '__all__' we add the error keyed to the given field name
                # `name` via `self.add_error`:
                # https://docs.djangoproject.com/en/2.0/ref/forms/validation/#cleaning-and-validating-fields-that-depend-on-each-other
                # note: pass only invalid_gsims as the result would be equal
                # than passing all gsims but the loop is faster:
                invalid_imts = imts - set(self.shared_imts(gsims))
                err_gsim = ValidationError(_("%(num)d gsim(s) not defined "
                                             "for all supplied imt(s)"),
                                           params={'num': len(invalid_gsims)},
                                           code='invalid')
                err_imt = ValidationError(_("%(num)d imt(s) not defined for "
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

        filter_exprs = (Q(imts__contains=imt_name) for imt_name in gsim_names)
        # multiple Q arguments to a lookup function (e.g. .filter) => AND:
        return models.Imt.objects.filter(*filter_exprs).\
            values_list('name', flat=True).distinct()

    @staticmethod
    def sharing_gsims(imt_names):
        """Returns a list of GSIM names sharing *all* the given IMTs

        :param imt_names: list of strings denoting GSIM names
        """
        if not imt_names:
            return []

        filter_exprs = (Q(imts__contains=imt_name) for imt_name in imt_names)
        # multiple Q arguments to a lookup function (e.g. .filter) => AND:
        return models.Gsim.objects.filter(*filter_exprs).\
            values_list('name', flat=True).distinct()


class APIForm(Form):
    """Form handling the validation of the format related argument in a request"""

    DATA_FORMAT_TEXT = 'text'
    DATA_FORMAT_JSON = 'json'

    @property
    def get_data_format(self):
        return self.data['data_format']

    data_format = ChoiceField(required=False, initial=DATA_FORMAT_JSON,
                              label='The format of the data returned',
                              choices=[(DATA_FORMAT_JSON, 'json'),
                                       (DATA_FORMAT_TEXT, 'text/csv')])

    csv_sep = TextSepField(required=False, initial='comma',
                           label='The (column) separator character',
                           help_text=('Ignored if the requested '
                                      'format is not text'))

    csv_dec = TextDecField(required=False, initial='period',
                           label='The decimal separator character',
                           help_text=('Ignored if the requested '
                                      'format is not text'))

    def clean(self):
        super().clean()
        tsep, tdec = 'text_sep', 'text_dec'
        # convert to symbols:
        if self.cleaned_data[tsep] == self.cleaned_data[tdec] and \
                self.cleaned_data['format'] == 'text':
            msg = _("'%s' must differ from '%s' in 'text' format" %
                    (tsep, tdec))
            err_ = ValidationError(msg, code='conflicting values')
            # add_error removes also the field from self.cleaned_data:
            self.add_error(tsep, err_)
            self.add_error(tdec, err_)

        return self.cleaned_data

    @property
    def response_data(self) -> Union[dict, StringIO, None]:
        """Return the response data by processing the form data, or None if
        the form is invalid (`self.is_valid() == False`)
        """
        if not self.is_valid():
            return None
        c_data = self.cleaned_data
        obj = self.process_data(c_data) or {}
        if self.cleaned_data['format'] == 'text':
            obj = self.to_csv_buffer(obj, c_data['text_sep'], c_data['text_dec'])
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
        wrt = csv.writer(buffer,
                         delimiter=sep,
                         quotechar='"',
                         quoting=csv.QUOTE_MINIMAL)

        # first build a list to get the maximum number of columns (for safety):
        rowsaslist = []
        maxcollen = 0
        comma_decimal = dec == ','
        for row in cls.csv_rows(processed_data):
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

        # # calculate the content length. This has to be done before creating
        # # the response as it might be that the latter closes the buffer. It
        # # is questionable then to use a buffer (we might use getvalue() on it
        # # but we pospone this check ...
        # buffer.seek(0, os.SEEK_END)
        # contentlength = buffer.tell()
        # buffer.seek(0)
        # # response = HttpResponse(buffer, content_type='text/csv')
        # # response['Content-Length'] = str(contentlength)
        # # return response
        return buffer

    @classmethod
    def csv_rows(cls, process_result) -> Iterable[list[str]]:
        """Yield lists of strings representing a csv row from the given
        process_result. the number of columns can be arbitrary and will be
        padded by `self.to_csv_buffer`
        """
        raise NotImplementedError(":meth:%s.csv_rows" % cls.__name__)

    # @classmethod
    # def convert_to_comma_as_decimal(cls, row):
    #     """Create a generator yielding each element of row where numeric
    #     values are converted to strings with comma as decimal separator.
    #     For non-float values, each row element is yielded as it is
    #
    #     @param row: a list of lists
    #     """
    #     for cell in row:
    #         if isinstance(cell, float):
    #             yield str(cell).replace('.', ',')
    #         else:
    #             yield cell

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


# FIXME: WHEN USED this, maybe replace in some other module:
from smtk.database_visualiser import DISTANCE_LABEL as SMTK_DISTANCE_LABEL
# Copy SMTK_DISTANCE_LABELS replacing the key 'r_x' with 'rx':
DISTANCE_LABEL = dict(
    **{k: v for k, v in SMTK_DISTANCE_LABEL.items() if k != 'r_x'},
    rx=SMTK_DISTANCE_LABEL['r_x']
)


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