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
from django.forms.widgets import Select
from django.forms.fields import BooleanField, CharField

from openquake.hazardlib.scalerel import get_available_magnitude_scalerel
from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib.imt import __all__ as available_imts  # FIXME: isn't there a nicer way?


# class ArrayField(CharField):
#     def __init__(self, *, max_length=None, min_length=None, strip=True, empty_value='', **kwargs):
#         
#         # Parameters after “*” or “*identifier” are keyword-only parameters
#         # and may only be passed used keyword arguments.
#         self.max_length = max_length
#         self.min_length = min_length
#         self.strip = strip
#         self.empty_value = empty_value
#         super().__init__(**kwargs)
#         if min_length is not None:
#             self.validators.append(validators.MinLengthValidator(int(min_length)))
#         if max_length is not None:
#             self.validators.append(validators.MaxLengthValidator(int(max_length)))
#         self.validators.append(validators.ProhibitNullCharactersValidator())
# 
#     def to_python(self, value):
#         """Return a string."""
#         if value not in self.empty_values:
#             value = str(value)
#             if self.strip:
#                 value = value.strip()
#         if value in self.empty_values:
#             return self.empty_value
#         return value
# 
#     def widget_attrs(self, widget):
#         attrs = super().widget_attrs(widget)
#         if self.max_length is not None and not widget.is_hidden:
#             # The HTML attribute is maxlength, not max_length.
#             attrs['maxlength'] = str(self.max_length)
#         if self.min_length is not None and not widget.is_hidden:
#             # The HTML attribute is minlength, not min_length.
#             attrs['minlength'] = str(self.min_length)
#         return attrs


class validation(object):
    
    @classmethod
    def isinragne(self, value, minval=None, maxval=None):
        return (minval is None or value >= minval) and (maxval is None or value <= maxval)
    
    @classmethod
    def parse2dpoint(cls, string, range1=None, range2=None):
        '''parses ``string`` into a 2-element tuple of floats, returning that
            tuple. Raises TypeError if the string is not parsable, raises ValueError
            if a range error occurs (if range1 and/or range2 are specified

        :param string: a string representing the 2d point. The string will be stripped (leading
            and trailing spaces omitted) and then splitted by searching a comma or a sequence of
            spaces
        :param range1: a list / tuple of two elements specifiying the lower and upper
            numeric bounds for the first parsed value (end-points are included in the match).
            If None (the default) no range check is performed
        :param range2: a list / tuple of two elements specifiying the lower and upper
            numeric bounds for the second parsed value (end-points are included in the match).
            If None (the default) no range check is performed

        :raises: ValueError if the string is malformed, or OverflowError in case of out-of-bounds
            value. In that case, the string of the OverflowError represents the portion
            of ``string`` whose value overflowed
        '''
        values = re.split("(?:,|\\s+)", string.strip())
        
        try:
            if len(values) != 2:
                raise TypeError()
            else:
                try:
                    val1 = float(values[0].strip())
                    val2 = float(values[1].strip())
                except ValueError:
                    raise TypeError()

                if range1 is not None and not cls.isinragne(val1, range1[0], range1[1]):
                    raise ValueError("%s not in %s" % (values[0].strip(), list(range1)))
                if range2 is not None and not cls.isinragne(val2, range2[0], range2[1]):
                    raise ValueError("%s not in %s" % (values[1].strip(), list(range2)))

                return (val1, val2)
        except TypeError:  # in order to make msg different from out of range error above
            raise ValueError(("'%s' not parsable as two space- "
                                  "or comma-separated floats") % string.split())

    @classmethod
    def validate_lonlat(cls, string):
        try:
            cls.parse2dpoint(string, range1=[-180, 180], range2=[-90, 90])
        except ValueError as err:
            raise ValidationError(str(err))

    @classmethod
    def validate_hyploc(cls, string):
        try:
            return cls.parse2dpoint(string, range1=[0, 1], range2=[0, 1])
        except ValueError as err:
            raise ValidationError(str(err))


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
    def isimtdefinedfor(cls, imt_name, gsim_name):
        return imt_name in cls.gsims2imts.get(gsim_name, [])


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
            if not isinstance(field.widget, BooleanField):
                atts['class'] = 'form-control'
            return atts 
        customize_widget_atts(self, ngfunc)
        
        #self.fields['my_checkbox'].widget.attrs.update({'onclick': 'return false;'})

    magnitude = forms.FloatField(label='Magnitude')
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
    initial_point = forms.CharField(label="Location on Earth",
                                    validators=[validation.validate_lonlat],
                                    initial="0 0",
                                    help_text='Longitude Latitude')
    hypocentre_location = forms.CharField(label=("Location of Hypocentre"),
                                          validators=[validation.validate_hyploc],
                                          initial="0.5 0.5",
                                          help_text='Along-strike fraction, Down-dip fraction')
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
        imt = cleaned_data.get("imt")
        
        if not gsims:
            raise forms.ValidationError("No Gsim selected")
        
        if not imt:
            raise forms.ValidationError("No Imt selected")
        

        for gsim_name in gsims:
            if not InputSelection.isimtdefinedfor(imt, gsim_name):
                raise forms.ValidationError(
                    _("%(imt) not defined for %(gsim)"), params={'imt': imt, 'gsim':gsim_name}
                )
                