'''
Django Forms stuff for eGSIM

Created on 29 Jan 2018

@author: riccardo
'''

import re
import json
from itertools import chain, repeat
from collections import OrderedDict

import numpy as np

from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from django.forms import Form
from django.utils.safestring import mark_safe
from django.forms.widgets import RadioSelect, CheckboxSelectMultiple, CheckboxInput,\
    HiddenInput
from django.forms.fields import BooleanField, CharField, MultipleChoiceField, FloatField, \
    ChoiceField, TypedChoiceField, MultiValueField
# from django.core import validators

from openquake.hazardlib import imt
from openquake.hazardlib.scalerel import get_available_magnitude_scalerel
from openquake.hazardlib.geo import Point
from smtk.trellis.configure import vs30_to_z1pt0_cy14, vs30_to_z2pt5_cb14
from smtk.trellis.trellis_plots import DistanceIMTTrellis, DistanceSigmaIMTTrellis, \
    MagnitudeIMTTrellis, MagnitudeSigmaIMTTrellis, MagnitudeDistanceSpectraTrellis, \
    MagnitudeDistanceSpectraSigmaTrellis

from egsim.utils import vectorize, EGSIM, isscalar, unique
from _io import StringIO
import yaml



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
        the same as `self.clean()`. But it's safe when the latter is overridden in order to
        return more complex and non-serializable objects.
        Moreover, note that if value (or any of its values) contains the colon, ':',
        then value is returned as it is

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
            raise ValidationError(str(exc))

    def clean(self, value):
        """Return a number or a list of numbers depending on `value`"""
        return self.serialize(value, parsecolon=True)
#         value = super(NArrayField, self).clean(value)
#         try:
#             return self.parsenarray(value, self.na_minlen, self.na_maxlen, self.min_value,
#                                     self.max_value)
#         except (ValueError, TypeError) as exc:
#             raise ValidationError(str(exc))

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

    def __init__(self, *args, **kwargs):
        super(IMTField, self).__init__(*args, **kwargs)
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


class BaseForm(Form):
    '''Base eGSIM form'''

    _gsims = EGSIM

    # fields (not used for rendering, just for validation): required is True by default
    gsim = MultipleChoiceField(label='Ground Shaking Intensity Model/s (gsim):',
                               choices=zip(_gsims.aval_gsims(), _gsims.aval_gsims()),
                               # make field.is_hidden = True in the templates:
                               widget=HiddenInput)

    imt = IMTField(label='Intensity Measure Type/s (imt)',
                   required=True,  # required jandled in clean()
                   # make field.is_hidden = True in the templates:
                   widget=HiddenInput)

#     sa_period = NArrayField(label='SA (period/s):',
#                             required=False,  # required jandled in clean()
#                             # make field.is_hidden = True in the templates:
#                             widget=HiddenInput)

    def __init__(self, *args, **kwargs):
        '''Overrides init to set custom attributes on field widgets and to set the initial
        value for fields of this class with no match in the keys of self.data'''
        # How do we implement custom attributes for js libraries (e.,g. bootstrap, angular...)?
        # All solutions (widget_tweaks, django-angular) are, as always, for big projects and they
        # are huge overheads for the goal we want to achieve.
        # So, after all we just need to overwrite few attributes on a form:
        super(BaseForm, self).__init__(*args, **kwargs)
        # now we want to re-name potential parameter names (e.g., 'mag' into 'magnitude')
        # To do this, define a __additional_fieldnames__ as class attribute, where
        # is a dict of name (string) mapped to its possible
        repl_dict = getattr(self, '__additional_fieldnames__', None)
        if repl_dict:
            for key in list(self.data.keys()):
                repl_key = repl_dict.get(key, None)
                if repl_key is not None:
                    self.data[repl_key] = self.data.pop(key)

        # https://stackoverflow.com/a/20309754:
        # Defaults are set accoridng to the initial value in the field
        # This must be set here cause in clean() required fields are processed before and their
        # error set in the error form
        for name in self.fields:
            if not self[name].html_name in self.data and self.fields[name].initial is not None:
                self.data[name] = self.fields[name].initial

        # put 'sa_periods in the IMTField:
        self.fields['imt'].sa_periods = self.data.pop('sa_periods', [])

        self.customize_widget_attrs()

    def to_dict(self):
        '''Converts this form to python dict. Each value is the `to_python` method of the
        corresponding django Field, or the serialize method of the NArrayFields. the latter
        converts the input to numeric array except the case when the input is given
        as range '<start>:<stop>:<end>': in this case, the string is returned as it is.

        raises ValidationError if the form is not valid
        '''
        if not self.is_valid():
            raise ValidationError(self.errors)

        return {name:
                self.fields[name].serialize(val) if isinstance(self.fields[name], NArrayField)
                else self.fields[name].to_python(val) for name, val in self.data.items()}

    def serialize(self, stream=None, syntax='yaml'):
        """Serialize this Form instance into a YAML stream.
           If stream is None, return the produced string instead.

           :param stream: A stream like a file-like object (in general any
               object with a write method) or None
            :param syntax: string, either 'json' or 'yaml'. If not either string, this
                method raises ValueError
        """
        syntax = syntax.lower()
        if syntax not in ('json', 'yaml'):
            raise ValueError("Form serialization syntax must be 'json' or 'yaml'")

        obj = self.to_dict()
        if syntax == 'json':  # JSON
            if stream is None:
                return json.dumps(obj, indent=2, separators=(',', ': '), sort_keys=True)
            else:
                json.dump(obj, stream, indent=2, separators=(',', ': '), sort_keys=True)
        else:  # YAML

            class MyDumper(yaml.SafeDumper):  # pylint: disable=too-many-ancestors
                '''forces indentation of lists. See https://stackoverflow.com/a/39681672'''
                def increase_indent(self, flow=False, indentless=False):
                    return super(MyDumper, self).increase_indent(flow, False)

            # inject comments in yaml by using the field label and the label help:
            stringio = StringIO() if stream is None else stream
            for name, value in obj.items():
                field = self.fields[name]
                label = field.label + ('' if not field.help_text else ' (%s)' % field.help_text)
                if label:
                    label = '# %s\n' % (label.replace('\n', ' ').replace('\r', ' '))
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

    def customize_widget_attrs(self):
        '''customizes the widget attributes (currently sets a bootstrap class on almost all
        of them'''
        atts = {'class': 'form-control'}  # for bootstrap
        for name, field in self.fields.items():  # @UnusedVariable
            # add class only for specific html elements, some other might have weird layout
            # if class 'form-control' is added on them:
            if not isinstance(field.widget, (CheckboxInput, CheckboxSelectMultiple, RadioSelect))\
                    and not field.widget.is_hidden:
                field.widget.attrs.update(atts)

    def clean(self):
        '''runs validation where we must validate selected gsim(s) based on selected intensity
        measure type. For info see:
        https://docs.djangoproject.com/en/1.11/ref/forms/validation/#cleaning-and-validating-fields-that-depend-on-each-other
        '''
        cleaned_data = super().clean()

        gsims = cleaned_data.get("gsim", [])
        # We need to reduce all IMT strings in cleaned_data['imt'] to a set
        # where all 'SA(#)' strings are counted as 'SA' once..
        # Use imt.from_string and get the class name: quite cumbersome, but it works
        imt_classnames = set(imt.from_string(imtname).__class__.__name__
                             for imtname in cleaned_data.get("imt", []))

        if gsims and imt_classnames:
            imts2 = self._gsims.shared_imts(*gsims)
            not_allowed = imt_classnames - imts2
            if not_allowed:
                raise ValidationError(_("'%(imt)s' not defined for all supplied gsim(s)"),
                                      params={'imt': str(not_allowed)})

        return cleaned_data


class MsrField(ChoiceField):
    _aval_msr = get_available_magnitude_scalerel()

    base_choices = tuple(zip(_aval_msr.keys(), _aval_msr.keys()))

    def __init__(self, **kwargs):  # * -> force the caller to use named arguments
        super(MsrField, self).__init__(choices=self.base_choices, **kwargs)

    def clean(self, value):
        value = ChoiceField.to_python(self, ChoiceField.clean(self, value))
        try:
            return self._aval_msr[value]()
        except Exception as exc:
            raise ValidationError(_(str(exc)))


class TrellisplottypeField(ChoiceField):
    '''Choice field which returns a tuple of Trelliplot classes from its clean()
    method (overridden'''
    _aval_types = \
        OrderedDict([
            ('d', ('IMT vs. Distance', DistanceIMTTrellis)),
            ('m', ('IMT vs. Magnitude', MagnitudeIMTTrellis)),
            ('s', ('Magnitude-Distance Spectra', MagnitudeDistanceSpectraTrellis)),
            ('ds', ('IMT vs. Distance (st.dev)', DistanceSigmaIMTTrellis)),
            ('ms', ('IMT vs. Magnitude  (st.dev)', MagnitudeSigmaIMTTrellis)),
            ('ss', ('Magnitude-Distance Spectra  (st.dev)',
                    MagnitudeDistanceSpectraSigmaTrellis))
            ])

    base_choices = tuple(zip(_aval_types.keys(), [v[0] for v in _aval_types.values()]))

    def __init__(self, **kwargs):  # * -> force the caller to use named arguments
        super(TrellisplottypeField, self).__init__(choices=self.base_choices, **kwargs)

    def clean(self, value):
        value = ChoiceField.to_python(self, ChoiceField.clean(self, value))
        try:
            return self._aval_types[value][1]
        except Exception as exc:
            raise ValidationError(_(str(exc)))


# https://docs.djangoproject.com/en/2.0/ref/forms/fields/#creating-custom-fields
class PointField(NArrayField):
    def __init__(self, **kwargs):
        super(PointField, self).__init__(min_arr_len=2, max_arr_len=3, **kwargs)

    def clean(self, value):
        value = NArrayField.clean(self, value)
        try:
            return Point(*value)
        except Exception as exc:
            raise ValidationError(_(str(exc)))


class TrellisForm(BaseForm):
    '''Form for Trellis plot generation'''

    __additional_fieldnames__ = {'mag': 'magnitude', 'dist': 'distances', 'tr': 'tectonic_region',
                                 'magnitude_scaling_relatio': 'msr', ',lineazi': 'line_azimuth',
                                 'vs30m': 'vs30_measured', 'hyploc': 'hypocentre_location'}

    __scalar_or_vector_help__ = 'Scalar, vector or range'

    plot_type = TrellisplottypeField(label='Plot type', initial="d")
    # GSIM RUPTURE PARAMS:
    magnitude = NArrayField(label='Magnitude(s)', min_arr_len=1,
                            help_text=__scalar_or_vector_help__)
    distance = NArrayField(label='Distance(s)', min_arr_len=1,
                           help_text=__scalar_or_vector_help__)
    dip = FloatField(label='Dip', min_value=0., max_value=90.)
    aspect = FloatField(label='Rupture Length / Width', min_value=0.)
    tectonic_region = CharField(label='Tectonic Region Type',
                                initial='Active Shallow Crust', widget=HiddenInput)
    rake = FloatField(label='Rake', min_value=-180., max_value=180., initial=0.)
    ztor = FloatField(label='Top of Rupture Depth (km)', min_value=0., initial=0.)
    strike = FloatField(label='Strike', min_value=0., max_value=360., initial=0.)
    msr = MsrField(label='Magnitude Scaling Relation', initial="WC1994")
    initial_point = PointField(label="Location on Earth", help_text='Longitude Latitude',
                               min_value=[-180, -90], max_value=[180, 90], initial="0 0")
    hypocentre_location = NArrayField(label="Location of Hypocentre", initial='0.5 0.5',
                                      help_text='Along-strike fraction, Down-dip fraction',
                                      min_arr_len=2, max_arr_len=2,
                                      min_value=[0, 0], max_value=[1, 1])
    # END OF RUPTURE PARAMS
    vs30 = NArrayField(label=mark_safe('VS30 (m/s)'), min_value=0., min_arr_len=1,
                       initial=760.0, help_text=__scalar_or_vector_help__)
    vs30_measured = BooleanField(label=mark_safe('Is VS30 measured'),
                                 help_text='Otherwise is inferred', initial=True, required=False)
    line_azimuth = FloatField(label='Azimuth of Comparison Line',
                              min_value=0., max_value=360., initial=0.)
    z1pt0 = NArrayField(label=mark_safe('Depth to 1 km/s V<sub>S</sub> layer (m)'),
                        min_value=0., required=False,
                        help_text=mark_safe("If empty, a default value will be calculated "
                                            "from the V<sub>S30</sub>"))
    z2pt5 = NArrayField(label=mark_safe('Depth to 2.5 km/s V<sub>S</sub> layer (km)'),
                        min_value=0., required=False,
                        help_text=mark_safe("If empty, a default value will be calculated "
                                            "from the V<sub>S30</sub>"))
    backarc = BooleanField(label='Backarc Path', initial=False, required=False)

    def clean(self):
        cleaned_data = super(TrellisForm, self).clean()
        vs30 = cleaned_data['vs30']  # surely a list with st least one element
        vs30scalar = isscalar(vs30)
        vs30s = np.array(vectorize(vs30), dtype=float)

        for name, func in (['z1pt0', vs30_to_z1pt0_cy14], ['z2pt5', vs30_to_z2pt5_cb14]):
            if name not in cleaned_data or cleaned_data[name] == []:
                values = func(vs30s)  # numpy-function
                cleaned_data[name] = float(values[0]) if vs30scalar else values.tolist()
            elif not isscalar(cleaned_data[name]) and not isscalar(vs30) \
                    and len(vs30) != len(cleaned_data[name]):
                raise ValidationError(_("'%(name)s' value must be scalar, empty or "
                                        "a %(num)d-elements vector"),
                                      params={'name': name, 'num': len(vs30)})
        return cleaned_data
