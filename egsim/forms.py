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
    ChoiceField, TypedChoiceField
# from django.core import validators

from openquake.hazardlib.scalerel import get_available_magnitude_scalerel
from smtk.trellis.configure import vs30_to_z1pt0_cy14, vs30_to_z2pt5_cb14
from smtk.trellis.trellis_plots import DistanceIMTTrellis, DistanceSigmaIMTTrellis, \
    MagnitudeIMTTrellis, MagnitudeSigmaIMTTrellis, MagnitudeDistanceSpectraTrellis, \
    MagnitudeDistanceSpectraSigmaTrellis

from egsim.utils import vectorize, Gsims, isscalar


# https://docs.djangoproject.com/en/2.0/ref/forms/fields/#creating-custom-fields
class NArrayField(CharField):
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

    def clean(self, value):
        """Return a number or a list of numbers depending on `value`"""
        value = super(NArrayField, self).clean(value)
        try:
            return self.parsenarray(value, self.na_minlen, self.na_maxlen, self.min_value,
                                    self.max_value)
        except (ValueError, TypeError) as exc:
            raise ValidationError(str(exc))

    RTOL = 1e-15
    ATOL = 0

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
                values.append(float(val))
            else:
                values += cls.str2nprange(val)

        # check lengths:
        try:
            cls.checkragne(len(values), minlen, maxlen)
        except ValueError as verr:  # just re-format exception string and raise:
            suffix = str(verr)[str(verr).find(' '):]
            raise ValueError('numbers count (%d)' % len(values) + suffix)

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
            raise TypeError("values must be strings or numbers, not '%s'" % str(val))

    @staticmethod
    def split(string):
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

        return re.split("(?:\\s*,\\s*|(?<!:)\\s+(?!:))", string)

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
        # check if we should include the end:
        ratio = (stop-start)/step
        # the relative tolerance below (tested) makes e.g. stop=10 and stop=9.9999999
        # NOT close, 10 and 9.99999999 close, as well as , e.g. 45 and 4.450000000000002
        if np.isclose(int(0.5+ratio), ratio, rtol=cls.RTOL, atol=cls.ATOL):
            stop += step
        return np.arange(start, stop, step, dtype=float).tolist()

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


class BaseForm(Form):
    '''Base eGSIM form'''

    _gsims = Gsims()

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

        self.customize_widget_attrs()

    def customize_widget_attrs(self):
        '''customizes the widget attributes (currently sets a bootstrap class on almost all
        of them'''
        atts = {'class': 'form-control'}  # for bootstrap
        for name, field in self.fields.items():
            # add class only for specific html elements, some other might have weird layout
            # if class 'form-control' is added on them:
            if not isinstance(field.widget, (CheckboxInput, CheckboxSelectMultiple, RadioSelect))\
                    and not field.widget.is_hidden:
                field.widget.attrs.update(atts)

    # fields (not used for rendering, just for validation): required is True by default
    gsim = MultipleChoiceField(label='Selected Ground Shaking Intensity Model/s (GSIM):',
                               choices=zip(_gsims.aval_gsims(), _gsims.aval_gsims()),
                               # make field.is_hidden = True in the templates:
                               widget=HiddenInput)

    imt = MultipleChoiceField(label='Selected Intensity Measure Type/s (IMT):',
                              choices=zip(_gsims.aval_imts(), _gsims.aval_imts()),
                              # make field.is_hidden = True in the templates:
                              widget=HiddenInput)

    def clean(self):
        '''runs validation where we must validate selected gsim(s) based on selected intensity
        measure type. For info see:
        https://docs.djangoproject.com/en/1.11/ref/forms/validation/#cleaning-and-validating-fields-that-depend-on-each-other
        '''
        cleaned_data = super().clean()

        gsims = cleaned_data.get("gsim", [])
        imts = set(cleaned_data.get("imt", []))

        if gsims and imts:
            imts2 = self._gsims.shared_imts(*gsims)
            not_allowed = imts - imts2
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
        value = ChoiceField.to_python(self, value)
        try:
            return self._aval_msr[value]()
        except Exception as exc:
            raise ValidationError(_(str(exc)))


class TrellisplottypeField(ChoiceField):
    _aval_types = \
        OrderedDict([('d', ('IMT vs. distance', DistanceIMTTrellis, DistanceSigmaIMTTrellis)),
                     ('m', ('IMT vs. Magnitude', MagnitudeIMTTrellis, MagnitudeSigmaIMTTrellis)),
                     ('s', ('Magnitude-Distance Spectra', MagnitudeDistanceSpectraTrellis,
                            MagnitudeDistanceSpectraSigmaTrellis))])

    base_choices = tuple(zip(_aval_types.keys(), [v[0] for v in _aval_types.values()]))

    def __init__(self, **kwargs):  # * -> force the caller to use named arguments
        super(TrellisplottypeField, self).__init__(choices=self.base_choices, **kwargs)

    def clean(self, value):
        value = ChoiceField.to_python(self, value)
        try:
            return self._aval_types[value][1:]
        except Exception as exc:
            raise ValidationError(_(str(exc)))


class TrellisForm(BaseForm):
    '''Form for Trellis plot generation'''

    __additional_fieldnames__ = {'mag': 'magnitude', 'dist': 'distances', 'tr': 'tectonic_region',
                                 'magnitude_scaling_relatio': 'msr', ',lineazi': 'line_azimuth',
                                 'vs30m': 'vs30_measured', 'hyploc': 'hypocentre_location'}

    plot_type = TrellisplottypeField(label='Plot type', initial="d")
    # GSIM RUPTURE PARAMS:
    magnitude = NArrayField(label='Magnitude(s)', min_arr_len=1)
    distance = NArrayField(label='Distance(s)', min_arr_len=1)
    dip = FloatField(label='Dip', min_value=0., max_value=90.)
    aspect = FloatField(label='Rupture Length / Width', min_value=0.)
    # tectonic_region = forms.CharField(label='Tectonic Region Type',
    #                                   initial='Active Shallow Crust')
    rake = FloatField(label='Rake', min_value=-180., max_value=180., initial=0.)
    ztor = FloatField(label='Top of Rupture Depth (km)', min_value=0., initial=0.)
    strike = FloatField(label='Strike', min_value=0., max_value=360., initial=0.)
    msr = MsrField(label='Magnitude Scaling Relation', initial="WC1994")
    initial_point = NArrayField(label="Location on Earth", initial="0 0",
                                help_text='Longitude Latitude', min_arr_len=2, max_arr_len=2,
                                min_value=[-180, -90], max_value=[180, 90])
    hypocentre_location = NArrayField(label="Location of Hypocentre", initial="0.5 0.5",
                                      help_text='Along-strike fraction, Down-dip fraction',
                                      min_arr_len=2, max_arr_len=2,
                                      min_value=[0, 0], max_value=[1, 1])
    # END OF RUPTURE PARAMS
    vs30 = NArrayField(label=mark_safe('V<sub>S30</sub>(s) (m/s)'), min_value=0., min_arr_len=1,
                       initial='760.0')
    vs30_measured = BooleanField(label=mark_safe('V<sub>S30</sub> measured '),
                                 help_text='Uncheck if inferred)', initial=True, required=False)
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
