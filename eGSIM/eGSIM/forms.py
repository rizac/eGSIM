'''
Created on 29 Jan 2018

@author: riccardo
'''

import re

from openquake.hazardlib.scalerel import get_available_magnitude_scalerel
from django.core.exceptions import ValidationError
from django import forms


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


class RuptureConfigForm(forms.Form):
    magnitude = forms.FloatField(label='Magnitude')
    dip = forms.FloatField(label='Dip', min_value=0., max_value=90.)
    aspect = forms.FloatField(label='Rupture Length / Width', min_value=0)
    tectonic_region = forms.CharField(label='Tectonic Region Type', initial='Active Shallow Crust')
    rake = forms.FloatField(label='Rake', min_value=-180., max_value=180., initial=0)
    ztor = forms.FloatField(label='Top of Rupture Depth (km)', min_value=0., initial=0)
    strike = forms.FloatField(label='Strike', min_value=0., max_value=360., initial=0)
    msr = forms.ChoiceField(label='Magnitude Scaling Relation',
                            choices=zip(get_available_magnitude_scalerel().keys(),
                                        get_available_magnitude_scalerel().keys()),
                            initial='WC1994')
    initial_point = forms.CharField(label="Location on Earth (Lon Lat)",
                                    validators=[validation.validate_lonlat],
                                    initial="0 0")
    hypocentre_location = forms.CharField(label=("Location of Hypocentre "
                                                 "(along-strike fraction, down-dip fraction)"),
                                    validators=[validation.validate_hyploc],
                                    initial="0.5 0.5")
    vs30 = forms.FloatField(label='V<sub>S30</sub>(m/s)', min_value=0., initial=760.0)
    vs30_measured = forms.BooleanField(label='V<sub>S30</sub> measured (uncheck if inferred)',
                                       initial=True)
    line_azimuth = forms.FloatField(label='Azimuth of Comparison Line',
                                    min_value=0., max_value=360., initial=0.)
    z1pt0 = forms.FloatField(label='Depth to 1 km/s V<sub>S</sub> layer (m)', min_value=0.,
                             required=False)
    z2pt5 = forms.FloatField(label='Depth to 2.5 km/s V<sub>S</sub> layer (km)', min_value=0.,
                             required=False)
    backarc = forms.BooleanField(label='Backarc Path', initial=False)
    