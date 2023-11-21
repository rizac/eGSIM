"""
Django Forms for eGSIM model-to-model comparison (Trellis plots)
"""
from django.forms import IntegerField
from itertools import cycle

import pandas as pd
from openquake.hazardlib.geo import Point
from openquake.hazardlib.scalerel import get_available_magnitude_scalerel
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.forms.fields import BooleanField, FloatField, ChoiceField, Field

from egsim.api.forms import APIForm, GsimImtForm
from egsim.smtk import get_trellis
from egsim.smtk.converters import dataframe2dict
from egsim.smtk.trellis import RuptureProperties, SiteProperties


_mag_scalerel = get_available_magnitude_scalerel()


class ArrayField(Field):
    """Implements an ArrayField. Loosely copied from
    django.contrib.postgres.forms.array.SplitArrayField (which unfortunately
    requires psycopg2)"""

    default_error_messages = {
        "invalid_size": "invalid number of elements: ",
    }

    def __init__(self, *base_fields:Field, **kwargs):
        """
        :param base_fields: the base field(s). 1-element means that
            this field accept a variable length array of values
        """
        assert len(set(type(_) for _ in base_fields)) == 1, \
            'base_fields must be of the same type'
        kwargs.setdefault("widget", base_fields[0].widget)
        if all (b.initial is not None for b in base_fields):
            kwargs.setdefault('initial', [b.initial for b in base_fields])
        super().__init__(**kwargs)
        self.base_fields = base_fields
        # override any error message with the error messages of the base field
        self.error_messages |= self.base_fields[0].error_messages

    def clean(self, value):
        cleaned_data = []
        if not value and self.required:
            raise ValidationError(self.error_messages["required"],
                                  code='required')
        if not isinstance(value, (list, tuple)):
            value = [value]
        size = len(self.base_fields)
        if 1 < size != len(value):
            raise ValidationError(self.error_messages['invalid_size'] +
                                  f'{str(len(value))} (expected {str(size)})',
                                  code='invalid_size')
        errors = []
        base_fields = self.base_fields
        if size == 1:
            base_fields = cycle(self.base_fields)
        for item, base_field in zip(value, base_fields):
            try:
                value = base_field.clean(item)
                cleaned_data.append(value)
            except ValidationError as error:
                errors.append(str(item))
        if errors:
            raise ValidationError(self.error_messages["invalid"],
                                  params={'value': ", ".join(errors)},
                                  code="invalid")
        return cleaned_data


class TrellisForm(GsimImtForm, APIForm):
    """Form for Trellis plot generation"""

    # Custom API param names (see doc of `EgsimBaseForm._field2params` for details):
    _field2params = {
        'magnitude': ['magnitude', 'mag'],
        'distance': ['distance', 'dist'],
        'msr': ['msr', 'magnitude-scalerel'],
        'vs30measured': ['vs30measured', 'vs30_measured'],
        'z1pt0': ['z1', 'z1pt0'],
        'initial_point': ['initial-point', 'initial_point'],
        'hypocentre_location': ['hypocenter-location',
                                'hypocentre-location',
                                'hypocenter_location',
                                'hypocentre_location', ],
        'line_azimuth': ['line-azimuth', 'line_azimuth'],
    }

    # GSIM RUPTURE PARAMS:
    magnitude = ArrayField(FloatField(), label='Magnitude(s)', required=True)
    distance = ArrayField(FloatField(), label='Distance(s)', required=True)
    vs30 = FloatField(label=mark_safe('V<sub>S30</sub> (m/s)'), initial=760.0)
    aspect = FloatField(label='Rupture Length / Width', min_value=0.)
    dip = FloatField(label='Dip', min_value=0., max_value=90.)
    rake = FloatField(label='Rake', min_value=-180., max_value=180.,
                      initial=0.)
    strike = FloatField(label='Strike', min_value=0., max_value=360.,
                        initial=0.)
    ztor = FloatField(label='Top of Rupture Depth (km)', min_value=0.,
                      initial=0.)
    # WARNING IF RENAMING FIELD BELOW: RENAME+MODIFY also `clean_msr`
    msr = ChoiceField(label='Magnitude-Area Scaling Relationship',
                      choices=[(_, _) for _ in _mag_scalerel],
                      initial="WC1994")
    # WARNING IF RENAMING FIELD BELOW: RENAME+MODIFY also `clean_location`
    initial_point = ArrayField(FloatField(initial=0, min_value=-180, max_value=180),
                               FloatField(initial=0, min_value=-90, max_value=90),
                               label="Location on Earth",
                               help_text='Longitude Latitude')
    hypocentre_location = ArrayField(FloatField(initial=0.5, min_value=0, max_value=1),
                                     FloatField(initial=0.5, min_value=0, max_value=1),
                                     label="Location of Hypocentre",
                                     help_text='Along-strike fraction, '
                                               'Down-dip fraction')
    region = IntegerField(label="Region parameter", min_value=0, max_value=5,
                          initial=0)
    # END OF RUPTURE PARAMS
    vs30measured = BooleanField(label=mark_safe('V<sub>S30</sub> is measured'),
                                help_text='Otherwise is inferred',
                                initial=True, required=False)
    line_azimuth = FloatField(label='Azimuth of Comparison Line',
                              min_value=0., max_value=360., initial=0.)
    z1pt0 = FloatField(label=mark_safe('Depth to 1 km/s V<sub>S</sub> layer (m)'),
                       help_text=mark_safe("Calculated from the "
                                           "V<sub>S30</sub> if not given"),
                       required=False)
    z2pt5 = FloatField(label=mark_safe('Depth to 2.5 km/s V<sub>S</sub> layer (km)'),
                       help_text=mark_safe("Calculated from the  "
                                            "V<sub>S30</sub> if not given"),
                       required=False)
    backarc = BooleanField(label='Backarc Path', initial=False, required=False)

    # All clean_<field> methods below are called in `self.full_clean` after each field
    # is validated individually in order to perform additional validation or casting:

    def clean_msr(self):
        """Clean the "msr" field by converting the given value to a
        object of type :class:`openquake.hazardlib.scalerel.base.BaseMSR`.
        """
        value = self.cleaned_data['msr']
        # https://docs.djangoproject.com/en/3.2/ref/forms/validation/
        # #cleaning-a-specific-field-attribute
        try:
            return _mag_scalerel[value]()
        except Exception as exc:
            raise ValidationError(str(exc), code='invalid')

    def clean_initial_point(self):
        """Clean the "location" field by converting the given value to a
        object of type :class:`openquake.hazardlib.geo.point.Point`.
        """
        value = self.cleaned_data['initial_point']
        # https://docs.djangoproject.com/en/3.2/ref/forms/validation/
        # #cleaning-a-specific-field-attribute
        try:
            return Point(*value)
        except Exception as exc:
            raise ValidationError(str(exc), code='invalid')

    @classmethod
    def response_data(cls, cleaned_data:dict) -> pd.DataFrame:
        return get_trellis(cleaned_data['gsim'],
                           cleaned_data['imt'],
                           cleaned_data['magnitude'],
                           cleaned_data['distance'],
                           RuptureProperties(**{p: cleaned_data[p] for p in
                                                RuptureProperties.__annotations__
                                                if p in cleaned_data}),
                           SiteProperties(**{p: cleaned_data[p] for p in
                                             SiteProperties.__annotations__
                                             if p in cleaned_data})
                           )

    # FIXME: REMOVE? is it used?
    @staticmethod
    def _default_periods_for_spectra():
        """Return an array for the default periods for the magnitude distance
        spectra trellis.
        The returned numeric list will define the xvalues of each plot
        """
        return [0.05, 0.075, 0.1, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.17, 0.18,
                0.19, 0.20, 0.22, 0.24, 0.26, 0.28, 0.30, 0.32, 0.34, 0.36, 0.38,
                0.40, 0.42, 0.44, 0.46, 0.48, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75,
                0.8, 0.85, 0.9, 0.95, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8,
                1.9, 2.0, 3.0, 4.0, 5.0, 7.5, 10.0]
