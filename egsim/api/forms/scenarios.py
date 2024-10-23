"""
Django Forms for eGSIM model-to-model comparison (Trellis plots)
"""
from itertools import cycle

import pandas as pd
from openquake.hazardlib.geo import Point
from openquake.hazardlib.scalerel import get_available_magnitude_scalerel
from django.core.exceptions import ValidationError
from django.forms.fields import BooleanField, FloatField, ChoiceField, Field

from egsim.api.forms import APIForm, GsimImtForm
from egsim.smtk import get_scenarios_predictions
from egsim.smtk.scenarios import RuptureProperties, SiteProperties


_mag_scalerel = get_available_magnitude_scalerel()


class ArrayField(Field):
    """Implements an ArrayField. Loosely copied from
    django.contrib.postgres.forms.array.SplitArrayField (which unfortunately
    requires psycopg2)"""

    def __init__(self, *base_fields: Field, **kwargs):
        """
        :param base_fields: the base field(s). 1-element means that
            this field accept a variable length array of values
        """
        assert len(set(type(_) for _ in base_fields)) == 1, \
            'base_fields must be of the same type'
        kwargs.setdefault("widget", base_fields[0].widget)
        if all(b.initial is not None for b in base_fields):
            kwargs.setdefault('initial', [b.initial for b in base_fields])
        super().__init__(**kwargs)
        self.base_fields = base_fields
        # override any error message with the error messages of the base field
        self.error_messages |= self.base_fields[0].error_messages

    def clean(self, value):
        cleaned_data = []
        if not value and self.required:
            raise ValidationError(APIForm.ErrMsg.required)
        if not isinstance(value, (list, tuple)):
            value = [value]
        size = len(self.base_fields)
        if 1 < size != len(value):
            raise ValidationError(f"expected {size} elements, not {len(value)}")
        base_fields = self.base_fields
        if size == 1:
            base_fields = cycle(self.base_fields)
        invalid = 0
        for item, base_field in zip(value, base_fields):
            try:
                cleaned_data.append(base_field.clean(item))
            except ValidationError:
                invalid += 1
        if invalid:
            raise ValidationError(f"{invalid} value"
                                  f"{'s are' if invalid != 1 else ' is'} "
                                  f"invalid")
        return [] if invalid else cleaned_data


class PredictionsForm(GsimImtForm, APIForm):
    """Form for the computation of Ground motion model predictions from
    different scenarios"""

    # Custom API param names (see doc of `EgsimBaseForm._field2params` for details):
    _field2params = {
        'magnitude': ('magnitude', 'mag'),
        'distance': ('distance', 'dist'),
        'msr': ('msr', 'magnitude-scalerel'),
        'vs30measured': ('vs30measured', 'vs30_measured'),
        'z1pt0': ('z1pt0', 'z1'),
        'initial_point': ('initial-point', 'initial_point'),
        'hypocenter_location': ('hypocenter-location',
                                'hypocentre-location',
                                'hypocentre_location'),
        'line_azimuth': ('line-azimuth', 'line_azimuth'),
    }

    # RUPTURE PARAMS:
    magnitude = ArrayField(FloatField(), help_text='Magnitudes', required=True)
    distance = ArrayField(FloatField(), help_text='Distances (km)', required=True)
    aspect = FloatField(
        help_text='Rupture Length / Width in [0, 1]', min_value=0., initial=1.0
    )
    dip = FloatField(
        min_value=0., max_value=90., initial=90,
        help_text="Dip of rupture (deg) in [0, 90]"
    )
    rake = FloatField(
        min_value=-180., max_value=180., initial=0.,
        help_text="Rake of rupture (deg) in [-180, 180]"
    )
    strike = FloatField(
        min_value=0., max_value=360., initial=0.,
        help_text="Strike of rupture (deg) in [0, 360]"
    )
    ztor = FloatField(help_text='Top of Rupture Depth (km)', min_value=0., initial=0.)
    # WARNING IF RENAMING FIELD BELOW: RENAME+MODIFY also `clean_msr`
    msr = ChoiceField(
        help_text='Magnitude-Area Scaling Relationship',
        choices=[(_, _) for _ in _mag_scalerel],
        initial="WC1994"
    )
    # WARNING IF RENAMING FIELD BELOW: RENAME+MODIFY also `clean_location`
    initial_point = ArrayField(
        FloatField(initial=0, min_value=-180, max_value=180),
        FloatField(initial=0, min_value=-90, max_value=90),
        help_text="Location on Earth (Longitude in [-180, 180], Latitude in [-90, 90])"
    )
    hypocenter_location = ArrayField(
        FloatField(initial=0.5, min_value=0, max_value=1),
        FloatField(initial=0.5, min_value=0, max_value=1),
        help_text="Location of Hypocenter (Along-strike fraction in [0, 1], "
                  "Down-dip fraction in [0, 1])")
    vs30 = FloatField(help_text="vs30 (m/s)", initial=760.0)

    # SITE PARAMS:
    region = ChoiceField(
        initial=0,
        choices=[
            (0, '0 - Default or unknown'),
            (1, '1 - Average / Slower'),
            (2, '2 - Average / Faster'),
            (3, '3 - Fast'),
            (4, '4 - Average'),
            (5, '5 - Very slow'),
        ],
        help_text="Attenuation cluster region "
                  "(https://doi.org/10.1007/s10518-020-00899-9)"
    )

    vs30measured = BooleanField(
        initial=True, required=False,
        help_text='Whether vs30 is measured (otherwise is inferred)'
    )
    line_azimuth = FloatField(
        help_text='Azimuth of Comparison Line in [0, 360]',
        min_value=0., max_value=360., initial=0.
    )
    z1pt0 = FloatField(
        required=False,
        help_text="Depth to 1 km/s Vs layer (m). If missing, it will be "
                  "calculated from the vs30"
    )
    z2pt5 = FloatField(
        required=False,
        help_text="Depth to 2.5 km/s Vs layer (km). If missing, it will be "
                  "calculated from the vs30"
    )
    backarc = BooleanField(help_text='Backarc Path', initial=False, required=False)

    @property
    def site_fields(self) -> dict[str, Field]:
        fields = set(SiteProperties.__annotations__) & set(self.base_fields)
        return {f: self.fields[f] for f in sorted(fields)}

    @property
    def rupture_fields(self) -> dict[str, Field]:
        fields = set(RuptureProperties.__annotations__) & set(self.base_fields)
        return {f: self.fields[f] for f in sorted(fields)}

    # All clean_<field> methods below are called in `self.full_clean` after each field
    # is validated individually in order to perform additional validation or casting:

    def clean_msr(self):
        """Clean the "msr" field by converting the given value to an
        object of type :class:`openquake.hazardlib.scalerel.base.BaseMSR`.
        """
        try:
            return _mag_scalerel[self.cleaned_data['msr']]()
        except Exception as exc:  # noqa
            raise ValidationError(self.ErrMsg.invalid)

    def clean_initial_point(self):
        """Clean the "location" field by converting the given value to an
        object of type :class:`openquake.hazardlib.geo.point.Point`.
        """
        try:
            return Point(*self.cleaned_data['initial_point'])
        except Exception as exc:  # noqa
            raise ValidationError(self.ErrMsg.invalid)

    def clean_region(self):
        """Clean the "region" field by converting the value (which is set as str
        by Django) to int.
        """
        try:
            return int(self.cleaned_data['region'])
        except Exception as exc:  # noqa
            raise ValidationError(self.ErrMsg.invalid)

    def output(self) -> pd.DataFrame:
        """Compute and return the output from the input data (`self.cleaned_data`).
        This method must be called after checking that `self.is_valid()` is True

        :return: any Python object (e.g., a JSON-serializable dict)
        """
        cleaned_data = self.cleaned_data
        rup = RuptureProperties(**{p: cleaned_data[p]
                                   for p in self.rupture_fields
                                   if p in cleaned_data})
        site = SiteProperties(**{p: cleaned_data[p] for p in
                                 self.site_fields
                                 if p in cleaned_data})
        return get_scenarios_predictions(cleaned_data['gsim'],
                                         cleaned_data['imt'],
                                         cleaned_data['magnitude'],
                                         cleaned_data['distance'],
                                         rupture_properties=rup,
                                         site_properties=site)
