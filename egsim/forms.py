'''
Created on 29 Jan 2018

@author: riccardo
'''

import re
import json

from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from django import forms
from django.utils.safestring import mark_safe
from django.forms.widgets import Select, RadioSelect, CheckboxSelectMultiple, CheckboxInput
from django.forms.fields import BooleanField, CharField

from openquake.hazardlib.scalerel import get_available_magnitude_scalerel
from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib.imt import __all__ as available_imts  # FIXME: isn't there a nicer way?
from django.core import validators
from itertools import chain, repeat


#https://docs.djangoproject.com/en/2.0/ref/forms/fields/#creating-custom-fields

class NArrayField(CharField):
    def __init__(self, *, min_arr_len=None, max_arr_len=None, bounds=None, **kwargs):
        '''
        Implements a numeric array field. Input is a string given as python list/tuple or js array.
        NOTE THAT brakets and commas are optional (if commas are missing, spaces will be used as
         separators, e.g. ".5 ,6.2 77" will result in [0.5, 6.2, 77] )
         
         :param min_arr_len: numeric (defaults to None) the minimum required length of the resulting
         numeric array. None means: no minlen required
         :param max_arr_len: numeric (defaults to None) the maximum required length of the resulting
         numeric array. None means: no maxlen required
         :param bounds: numeric list/tuple/ndarray of two values denoting the minimum and maximum
         values for the corresponding parsed element. If an elements of ``bounds`` is None or
         ``[None, None]``, the corresponding element is not checked. If ``bounds`` is None, no
         element will be checked. If ``bounds`` length is lower than the parsed
         array length, ``bounds`` will be padded with None's.
         :param kwargs: keyword arguments forwarded to the super-class.         
        '''
        # Parameters after “*” or “*identifier” are keyword-only parameters
        # and may only be passed used keyword arguments.
        super(NArrayField, self).__init__(**kwargs)
        self.na_minlen = min_arr_len
        self.na_maxlen = max_arr_len
        self.na_bounds = bounds or []
        
    def clean(self, value):
        """Return a string."""
        value = super(NArrayField, self).clean(value)
        return validation.parsenarray(value, self.na_minlen, self.na_maxlen, *self.na_bounds)


class validation(object):
    
    @classmethod
    def isinragne(self, value, minval=None, maxval=None):
        return (minval is None or value >= minval) and (maxval is None or value <= maxval)
    
    @classmethod
    def parsenarray(cls, string, minlen=None, maxlen=None, *bounds):
        '''parses ``string`` into a N-element list of floats, returning that
            list.

        :param minlen: numeric (defaults to None) the minimum required length of the resulting
         numeric array. None means: no minlen required
         :param maxlen: numeric (defaults to None) the maximum required length of the resulting
         numeric array. None means: no maxlen required
         :param bounds: numeric list/tuple/ndarray of two values denoting the minimum and maximum
         values for the corresponding parsed element. If an elements of ``bounds`` is None or
         ``[None, None]``, the corresponding element is not checked. If ``bounds`` is None, no
         element will be checked. If ``bounds`` length is lower than the parsed
         array length, ``bounds`` will be padded with None's.

        :raises: TypeError if the string is malformed
        '''
        string = string.strip()

        if string[0] in ('[', '('):
            if not string[-1] == {'[' :']', '(': ')'}[string[0]]:
                raise TypeError('unbalanced brackets')
            string = string.strip()

        values = re.split("(?:\\s*,\\s*|\\s+)", string)

        if minlen is not None and len(values) < minlen:
            if minlen == maxlen:
                raise TypeError('%d numbers required' % minlen)
            raise TypeError('at least %d numbers required' % minlen)
        if maxlen is not None and len(values) > maxlen:
            raise TypeError('not more than %d numbers required' % maxlen)
        
        ret = []
        
        for val, bound in zip(values, chain(bounds, repeat(None))):
            try:
                numval = float(val.strip())
            except ValueError:
                raise TypeError("nan: '%s'" % val)
            
            if bound is not None and not cls.isinragne(numval, bound[0], bound[1]):
                raise ValueError("%s not in %s" % (values[0].strip(), list(bound)))
            
            ret.append(numval)
        
        return ret


def customize_widget_atts(form, func):
    '''Customizes widget attributes. Although there are plenty of libraries out there
    (including integration with angularjs) most of which are a better approach
    (as they force to write view code in templates rather than here),
    this is the best solution found when comparing benefits over costs)
    
    :param func: a custom function returning a dict of keys mapped to their values, representing
        the attributes to be added to the current form widget.
        The function accepts three arguments:
        ```(field_name, field_object, fields_dict)```
        where field name is the field name (string)
        field_object is the field object whose ``field.widget`` returns the used django widget
        fields_dict is the parent dict of field names -> field objects this function is
            iterating over
        ```
    '''
    for name, field in form.fields.items():
        atts = func(name, field, form.fields)
        if not atts:
            continue
        field.widget.attrs.update(atts)


class InputSelection(object):
    '''Just a wrapper housing input selection stuff'''
    available_gsims = get_available_gsims()
    
    available_gsims_names = available_gsims.keys()

    available_imts_names = list(available_imts)
    
    gsims2imts = {key: set([imt.__name__ for imt in gsim.DEFINED_FOR_INTENSITY_MEASURE_TYPES])
                  for key, gsim in available_gsims.items()}
    
    gsim2trts = {key: gsim.DEFINED_FOR_TECTONIC_REGION_TYPE
                 for key, gsim in available_gsims.items()}
    
    @classmethod
    def get_available_gsims_json(cls):
        return [(g_name, list(cls.gsims2imts.get(g_name, [])), cls.gsim2trts.get(g_name, ''))
                for g_name in cls.available_gsims_names]
    
    @classmethod
    def imtdefinedfor(cls, gsim_name, *imt_names):
        return all(imt_name in cls.gsims2imts.get(gsim_name, []) for imt_name in imt_names)


class RuptureConfigForm(forms.Form):
    
    
    def __init__(self, *args, **kwargs):
        '''Overides init to set custom attributes on field widgets'''
        # Ok here is the deal: we want for the moment to delegat angularjs for most
        # of the work. We therefore need to set custom attrs to form fields in order
        # to make angular work properly. This might be REALLY NICELY ACHIEVED via
        # template rendering, so that the modifications are in the view.
        # We found widget_tweaks, but it doesn't allow detailed customization such as writing own expressions
        # it fails with select statements ngValue etcetera. Moreover, it seems about not to be
        # maintained anymore. We therefore tries to look at django-angular: too big learning curve,
        # unclear installation procedure involving npm and angular (how their js packages are downloaded
        # then?). So, after all we just need to overwrite few attributes on a form:
        super(RuptureConfigForm, self).__init__(*args, **kwargs)
        # customize our form fields to make it angular-compliant:
        def ngfunc(name, field, fields):
            atts = {}
            atts['ng-model'] = "form.%s" % name
            atts['ng-init'] = "form.%s=%s" % (name, json.dumps(field.initial))
            # atts['ng-show'] = "showField('%s')" % name
            if not isinstance(field.widget, (CheckboxInput, CheckboxSelectMultiple, RadioSelect)):
                atts['class'] = 'form-control'
            return atts 
        customize_widget_atts(self, ngfunc)
        
        #self.fields['my_checkbox'].widget.attrs.update({'onclick': 'return false;'})

    # GSIM RUPTURE PARAMS:
    magnitudes = NArrayField(label='Magnitudes', min_arr_len=1) 
    distances = NArrayField(label='Distances', min_arr_len=1)
    dip = forms.FloatField(label='Dip', min_value=0., max_value=90.)
    aspect = forms.FloatField(label='Rupture Length / Width', min_value=0.)
    # tectonic_region = forms.CharField(label='Tectonic Region Type', initial='Active Shallow Crust')
    rake = forms.FloatField(label='Rake', min_value=-180., max_value=180., initial=0.)
    ztor = forms.FloatField(label='Top of Rupture Depth (km)', min_value=0., initial=0.)
    strike = forms.FloatField(label='Strike', min_value=0., max_value=360., initial=0.)
    msr = forms.ChoiceField(label='Magnitude Scaling Relation',
                            choices=zip(get_available_magnitude_scalerel().keys(),
                                        get_available_magnitude_scalerel().keys()),
                            initial="WC1994")
    initial_point = NArrayField(label="Location on Earth", initial="0 0",
                                help_text='Longitude Latitude',
                                min_arr_len=2, max_arr_len=2, bounds=[[-180, 180], [-90, 90]])
    hypocentre_location = NArrayField(label="Location of Hypocentre", initial="0.5 0.5",
                                      help_text='Along-strike fraction, Down-dip fraction',
                                      min_arr_len=2, max_arr_len=2, bounds=[[0, 1], [0, 1]])
    # END OF RUPTURE PARAMS
    vs30 = forms.FloatField(label=mark_safe('V<sub>S30</sub> (m/s)'), min_value=0., initial=760.0)
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
    

class InputSelectionForm(forms.Form):
    
    # fields (not used for rendering, just for validation):
    gsims = forms.MultipleChoiceField(label='gsims',
                                      choices=zip(InputSelection.available_gsims_names,
                                                  InputSelection.available_gsims_names),
                                      initial=[])
    
    imt = forms.ChoiceField(label='imt',
                            choices=zip(InputSelection.available_imts_names,
                                        InputSelection.available_imts_names),
                            )
    
    def clean(self):
        '''runs validation where we must validate selected gsim(s) based on selected intensity
        measure type. For info see:
        https://docs.djangoproject.com/en/1.11/ref/forms/validation/#cleaning-and-validating-fields-that-depend-on-each-other
        '''
        cleaned_data = super().clean()
        gsims = cleaned_data.get("gsims")
        imts = cleaned_data.get("imts")
        
        if not gsims:
            raise forms.ValidationError("No Gsim selected")
        
        if not imts:
            raise forms.ValidationError("No Imt selected")
        

        for gsim_name in gsims:
            if not InputSelection.imtdefinedfor(gsim_name, *imts):
                raise forms.ValidationError(
                    _("%(imt) not all defined for %(gsim)"), params={'imts': imts, 'gsim':gsim_name}
                )

        return cleaned_data
                