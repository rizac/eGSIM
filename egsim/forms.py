'''
Created on 29 Jan 2018

@author: riccardo
'''

import re
import json

import numpy as np
from itertools import chain, repeat

from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from django import forms
from django.utils.safestring import mark_safe
from django.forms.widgets import Select, RadioSelect, CheckboxSelectMultiple, CheckboxInput, HiddenInput
from django.forms.fields import BooleanField, CharField
from django.core import validators

from openquake.hazardlib.scalerel import get_available_magnitude_scalerel
from smtk.trellis.configure import vs30_to_z1pt0_cy14, vs30_to_z2pt5_cb14

from egsim.utils import InitData, vectorize


#https://docs.djangoproject.com/en/2.0/ref/forms/fields/#creating-custom-fields

class NArrayField(CharField):
    def __init__(self, *, min_arr_len=None, max_arr_len=None, min_value=None, max_value=None,
                 **kwargs):
        '''
        Implements a numeric array field. Input is a string given as python list/tuple or js array,
        with optional brackets and optional commas if at least one space separates each element.
        Supported also is matlab vectors notation with colons (sort of numpy arange).

        Example: ".5 ,6.2 77 0:2:3" will result in [0.5, 6.2, 77 0 2] )

         :param min_arr_len: numeric (defaults to None) the minimum required length of the resulting
         numeric array. None means: no minlen required
         :param max_arr_len: numeric (defaults to None) the maximum required length of the resulting
         numeric array. None means: no maxlen required
         :param min_value: numeric, None or numeric array. If numeric, it sets the minimum required
         value for all parsed elements during validation. If None, it does not set a minimum value,
         if numeric array, sets the minimum values of the parsed elements: if the length is lower
         than the parsed elements length, it will be padded with None (do not check exceeding
         elements)
         :param max_value: numeric, None or numeric array. If numeric, it sets the maximum required
         value for all parsed elements during validation. If None, it does not set a minimum value,
         if numeric array, sets the minimum values of the parsed elements: if the length is lower
         than the parsed elements length, it will be padded with None (do not check exceeding
         elements)
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
        """Return a string."""
        value = super(NArrayField, self).clean(value)
        try:
            return validation.parsenarray(value, self.na_minlen, self.na_maxlen, self.min_value,
                                          self.max_value)
        except Exception as exc:
            raise forms.ValidationError(str(exc))


class validation(object):

    RTOL = 1e-15
    ATOL = 0

    @classmethod
    def isinragne(cls, value, minval=None, maxval=None):
        try:
            cls.checkragne(value, minval, maxval)
        except ValueError:
            return False

    @classmethod
    def checkragne(self, value, minval=None, maxval=None):
        if (minval is None or value >= minval) and (maxval is None or value <= maxval):
            return
        if minval is not None and maxval is not None:
            raise ValueError('%s not in [%s, %s]' % (str(value), str(minval), str(maxval)))
        elif minval is not None:
            raise ValueError('%s < %s' % (str(value), str(minval)))
        else:
            raise ValueError('%s > %s' % (str(value), str(maxval)))

    @classmethod
    def parsenarray(cls, string, minlen=None, maxlen=None, minval=None, maxval=None):
        '''parses ``string`` into a N-element list of floats, returning that
            list.

        See :ref:class:`NArrayField` init method for details
        :raises: TypeError if the string is malformed
        '''
        try:
            return float(string)
        except ValueError:
            pass
        except:  # @IgnorePep8 pylint:disable=bare-except
            raise TypeError('argument must be string or number')

        string = string.strip()

        if not string:
            return []

        if string[0] in ('[', '('):
            if not string[-1] == {'[': ']', '(': ')'}[string[0]]:
                raise TypeError('unbalanced brackets')
            string = string[1:-1].strip()

        values = []
        for val in re.split("(?:\\s*,\\s*|(?<!:)\\s+(?!:))", string):
            try:
                msg = 'nan'
                if ':' not in val:
                    values.append(float(val))
                    continue
                msg = "invalid range"
                # parse semicolon as in matlab: 1:3 = [1,2,3],  1:2:3 = [1,3]
                spl = [_.strip() for _ in val.split(':')]
                if len(spl) < 2 or len(spl) > 3:
                    raise TypeError()
                start, step, stop = \
                    float(spl[0]), 1 if len(spl) == 2 else float(spl[1]), float(spl[-1])
                # check if we should include the end:
                ratio = (stop-start)/step
                # the relative tolerance below (tested) makes e.g. stop=10 and stop=9.9999999 NOT
                # close, 10 and 9.99999999 close, as well as , e.g. 45 and 4.450000000000002
                if np.isclose(int(0.5+ratio), ratio, rtol=cls.RTOL, atol=cls.ATOL):
                    stop += step
                array = np.arange(start, stop, step, dtype=float).tolist()
                values += array
            except (TypeError, ValueError):
                raise TypeError("%s: '%s'" % (msg, val))

        if minlen is not None and len(values) < minlen:
            if minlen == maxlen:
                raise TypeError('%d numbers required' % minlen)
            raise TypeError('at least %d numbers required' % minlen)
        if maxlen is not None and len(values) > maxlen:
            raise TypeError('at most %d numbers required' % maxlen)

        # check bounds:
        minval = [] if minval is None else vectorize(minval)
        maxval = [] if maxval is None else vectorize(maxval)
        for numval, mnval, mxval in zip(values, chain(minval or [], repeat(None)),
                                        chain(maxval or [], repeat(None))):

            cls.checkragne(numval, mnval, mxval)

        return values


class BaseForm(forms.Form):

    def __init__(self, *args, **kwargs):
        '''Overides init to set custom attributes on field widgets'''
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
        atts = {'class': 'form-control'}  # for bootstrap
        for name, field in self.fields.items():
            if not isinstance(field.widget, (CheckboxInput, CheckboxSelectMultiple, RadioSelect))\
                    and not field.widget.is_hidden:
                field.widget.attrs.update(atts)

    # fields (not used for rendering, just for validation): required is True by default
    gsim = forms.MultipleChoiceField(label='Selected Ground Shaking Intensity Model/s (GSIM):',
                                     choices=zip(InitData.available_gsims_names,
                                                 InitData.available_gsims_names),
                                     # make field.is_hidden = True in the templates:
                                     widget=HiddenInput)

    imt = forms.MultipleChoiceField(label='Selected Intensity Measure Type/s (IMT):',
                                    choices=zip(InitData.available_imts_names,
                                                InitData.available_imts_names),
                                    # make field.is_hidden = True in the templates:
                                    widget=HiddenInput)

    def clean(self):
        '''runs validation where we must validate selected gsim(s) based on selected intensity
        measure type. For info see:
        https://docs.djangoproject.com/en/1.11/ref/forms/validation/#cleaning-and-validating-fields-that-depend-on-each-other
        '''
        cleaned_data = super().clean()

        gsims = cleaned_data.get("gsim", [])
        imts = cleaned_data.get("imt", [])

        for gsim_name in gsims:
            if not InitData.imtdefinedfor(gsim_name, *imts):
                raise forms.ValidationError(
                    _("imt '%(imt)s' not defined for all supplied gsim(s)"),
                    params={'imt': imts})

        return cleaned_data


class TrellisForm(BaseForm):

    __additional_fieldnames__ = {'mag': 'magnitude', 'dist': 'distances', 'tr': 'tectonic_region',
                                 'magnitude_scaling_relatio': 'msr', ',lineazi': 'line_azimuth',
                                 'vs30m': 'vs30_measured', 'hyploc': 'hypocentre_location'}

    def __init__(self, *args, **kwargs):
        '''Overides init to set custom attributes on field widgets'''
        # How do we implement custom attributes for js libraries (e.,g. bootstrap, angular...)?
        # All solutions (widget_tweaks, django-angular) are, as always, for big projects and they
        # are huge overheads for the goal we want to achieve.
        # So, after all we just need to overwrite few attributes on a form:
        super(TrellisForm, self).__init__(*args, **kwargs)

        # self.fields['my_checkbox'].widget.attrs.update({'onclick': 'return false;'})

    # GSIM RUPTURE PARAMS:
    magnitude = NArrayField(label='Magnitude(s)', min_arr_len=1)
    distance = NArrayField(label='Distance(s)', min_arr_len=1)
    dip = forms.FloatField(label='Dip', min_value=0., max_value=90.)
    aspect = forms.FloatField(label='Rupture Length / Width', min_value=0.)
    # tectonic_region = forms.CharField(label='Tectonic Region Type',
    #                                   initial='Active Shallow Crust')
    rake = forms.FloatField(label='Rake', min_value=-180., max_value=180., initial=0.)
    ztor = forms.FloatField(label='Top of Rupture Depth (km)', min_value=0., initial=0.)
    strike = forms.FloatField(label='Strike', min_value=0., max_value=360., initial=0.)
    msr = forms.ChoiceField(label='Magnitude Scaling Relation',
                            choices=zip(get_available_magnitude_scalerel().keys(),
                                        get_available_magnitude_scalerel().keys()),
                            initial="WC1994")
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
    vs30_measured = forms.BooleanField(label=mark_safe('V<sub>S30</sub> measured '),
                                       help_text='Uncheck if inferred)',
                                       initial=True, required=False)
    line_azimuth = forms.FloatField(label='Azimuth of Comparison Line',
                                    min_value=0., max_value=360., initial=0.)
    z1pt0 = forms.FloatField(label=mark_safe('Depth to 1 km/s V<sub>S</sub> layer (m)'),
                             min_value=0., required=False,
                             help_text=mark_safe("If empty, a default value will be calculated "
                                                 "from the V<sub>S30</sub>"))
    z2pt5 = forms.FloatField(label=mark_safe('Depth to 2.5 km/s V<sub>S</sub> layer (km)'),
                             min_value=0., required=False,
                             help_text=mark_safe("If empty, a default value will be calculated "
                                                 "from the V<sub>S30</sub>"))
    backarc = forms.BooleanField(label='Backarc Path', initial=False, required=False)

    def clean(self):
        cleaned_data = super(TrellisForm, self).clean()
        for name, func in (['z1pt0', vs30_to_z1pt0_cy14], ['z2pt5', vs30_to_z2pt5_cb14]):
            if name not in cleaned_data or cleaned_data[name] is None:
                cleaned_data[name] = func(cleaned_data['vs30'])
        return cleaned_data
