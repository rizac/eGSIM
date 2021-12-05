"""
Django Forms for eGSIM model-to-model comparison (Trellis plots)
"""
from collections import defaultdict
from enum import Enum
from itertools import chain, repeat
from typing import Iterable

import numpy as np
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext as _
from django.utils.safestring import mark_safe
from django.forms.fields import (BooleanField, FloatField, ChoiceField)
from openquake.hazardlib.geo import Point
from openquake.hazardlib.scalerel import get_available_magnitude_scalerel
from smtk.trellis.configure import vs30_to_z1pt0_cy14, vs30_to_z2pt5_cb14
from smtk.trellis.trellis_plots import (DistanceIMTTrellis,
                                        MagnitudeIMTTrellis,
                                        DistanceSigmaIMTTrellis,
                                        MagnitudeSigmaIMTTrellis,
                                        MagnitudeDistanceSpectraTrellis,
                                        MagnitudeDistanceSpectraSigmaTrellis)

from .. import (vectorize, isscalar, GsimImtForm, NArrayField, relabel_sa,
                APIForm)


class PointField(NArrayField):
    """NArrayField which validates a 2-element iterable and returns an
    OpenQuake Point"""

    def __init__(self, **kwargs):  # FIXME: depth? should be >0 in case ?
        super(PointField, self).__init__(min_count=2, max_count=2, **kwargs)

    def clean(self, value):
        """Converts the given value to a
        :class:`openquake.hazardlib.geo.point.Point` object.
        It is usually better to perform these types of conversions
        subclassing `clean`, as the latter is called at the end of the
        validation workflow
        """
        value = NArrayField.clean(self, value)
        try:
            return Point(*value)
        except Exception as exc:
            raise ValidationError(_(str(exc)), code='invalid')

# FIXME REMOVE
# class MsrField(DictChoiceField):
#     """A ChoiceField handling the selected Magnitude Scaling Relation object"""
#     _base_choices = get_available_magnitude_scalerel()


PLOT_TYPE = {
    # key: (display label, trellis class, stddev trellis class)
    'd': ('IMT vs. Distance', DistanceIMTTrellis, DistanceSigmaIMTTrellis),
    'm': ('IMT vs. Magnitude', MagnitudeIMTTrellis, MagnitudeSigmaIMTTrellis),
    's': ('Magnitude-Distance Spectra', MagnitudeDistanceSpectraTrellis,
          MagnitudeDistanceSpectraSigmaTrellis)
}


class TrellisForm(GsimImtForm, APIForm):
    """Form for Trellis plot generation"""

    _mag_scalerel = get_available_magnitude_scalerel()

    def fieldname_aliases(self, mapping):
        """Set field name aliases (exposed to the user as API parameter aliases):
        call `super()` and then for any field alias: `mapping[new_name]=name`
        See `EgsimBaseForm.__init__` for details
        """
        super().fieldname_aliases(mapping)
        mapping['mag'] = 'magnitude'
        mapping['dist'] = 'distance'
        mapping['stddev'] = 'stdev'
        mapping['tr'] = 'tectonic_region'
        mapping['msr'] = 'magnitude_scalerel'
        mapping['lineazi'] = 'line_azimuth'
        mapping['vs30m'] = 'vs30_measured'
        mapping['hyploc'] = 'hypocentre_location'
        mapping['vs30measured'] = 'vs30_measured'

    plot_type = ChoiceField(label='Plot type',
                            choices=[(k, v[0]) for k, v in PLOT_TYPE.items()])
    stdev = BooleanField(label='Compute Standard Deviation(s)', required=False,
                         initial=False)

    # GSIM RUPTURE PARAMS:
    magnitude = NArrayField(label='Magnitude(s)', min_count=1)
    distance = NArrayField(label='Distance(s)', min_count=1)
    vs30 = NArrayField(label=mark_safe('V<sub>S30</sub> (m/s)'), min_value=0.,
                       min_count=1, initial=760.0)
    aspect = FloatField(label='Rupture Length / Width', min_value=0.)
    dip = FloatField(label='Dip', min_value=0., max_value=90.)
    rake = FloatField(label='Rake', min_value=-180., max_value=180.,
                      initial=0.)
    strike = FloatField(label='Strike', min_value=0., max_value=360.,
                        initial=0.)
    ztor = FloatField(label='Top of Rupture Depth (km)', min_value=0.,
                      initial=0.)
    magnitude_scalerel = ChoiceField(label='Magnitude Scaling Relation',
                                     choices=[(_,_) for _ in _mag_scalerel],
                                     initial="WC1994")
    initial_point = PointField(label="Location on Earth",
                               help_text='Longitude Latitude', initial="0 0",
                               min_value=[-180, -90], max_value=[180, 90])
    hypocentre_location = NArrayField(label="Location of Hypocentre",
                                      initial='0.5 0.5',
                                      help_text=('Along-strike fraction, '
                                                 'Down-dip fraction'),
                                      min_count=2, max_count=2,
                                      min_value=[0, 0], max_value=[1, 1])
    # END OF RUPTURE PARAMS
    vs30_measured = BooleanField(label=mark_safe('Is V<sub>S30</sub> '
                                                 'measured?'),
                                 help_text='Otherwise is inferred',
                                 initial=True, required=False)
    line_azimuth = FloatField(label='Azimuth of Comparison Line',
                              min_value=0., max_value=360., initial=0.)
    z1pt0 = NArrayField(label=mark_safe('Depth to 1 km/s V<sub>S</sub> '
                                        'layer (m)'),
                        min_value=0., required=False,
                        help_text=mark_safe("Calculated from the "
                                            "V<sub>S30</sub> if not given"))
    z2pt5 = NArrayField(label=mark_safe('Depth to 2.5 km/s V<sub>S</sub> '
                                        'layer (km)'),
                        min_value=0., required=False,
                        help_text=mark_safe("Calculated from the  "
                                            "V<sub>S30</sub> if not given"))
    backarc = BooleanField(label='Backarc Path', initial=False, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If the plot_type is spectra, remove imt and sa_period
        # and set the field as not required, so validation will be ok:
        if self.data.get('plot_type', '') in ('s', 'ss'):
            self.fields['imt'].sa_periods_str = ''  # see superclass __init__
            self.data.pop('imt', None)
            self.data.pop('sa_period', None)
            self.fields['imt'].required = False
            self.fields['sa_period'].required = False  # for safety

    def clean(self):
        GsimImtForm.clean(self)
        APIForm.clean(self)
        cleaned_data = self.cleaned_data

        # Convert MSR to associated class:
        cleaned_data['magnitude_scalerel'] = \
            self._mag_scalerel[cleaned_data['magnitude_scalerel']]

        # calculate z1pt0 and z2pt5 if needed, raise in case of errors:
        vs30 = cleaned_data['vs30']  # surely a list with st least one element
        vs30scalar = isscalar(vs30)
        vs30s = np.array(vectorize(vs30), dtype=float)

        # check vs30-dependent values:
        for name, func in (['z1pt0', vs30_to_z1pt0_cy14],
                           ['z2pt5', vs30_to_z2pt5_cb14]):
            if name not in cleaned_data or cleaned_data[name] == []:
                values = func(vs30s)  # numpy-function
                cleaned_data[name] = \
                    float(values[0]) if vs30scalar else values.tolist()
            elif isscalar(cleaned_data[name]) != isscalar(vs30) or \
                    (not isscalar(vs30) and
                     len(vs30) != len(cleaned_data[name])):
                str_ = 'scalar' if isscalar(vs30) else \
                    '%d-elements vector' % len(vs30)
                # instead of raising ValidationError, which is keyed with
                # '__all__' we add the error keyed to the given field name
                # `name` via `self.add_error`:
                # https://docs.djangoproject.com/en/2.0/ref/forms/validation/#cleaning-and-validating-fields-that-depend-on-each-other
                error = ValidationError(_("value must be consistent with vs30 "
                                          "(%s)" % str_),
                                        code='invalid')
                self.add_error(name, error)

        return cleaned_data

    @classmethod
    def csv_rows(cls, process_result) -> Iterable[list[str]]:
        """Yield lists of strings representing a csv row from the given
        process_result. the number of columns can be arbitrary and will be
        padded by `self.to_csv_buffer`
        """
        yield ['imt', 'gsim', 'magnitude', 'distance', 'vs30']
        yield chain(repeat('', 5), [process_result['xlabel']],
                    process_result['xvalues'])
        for imt in process_result['imts']:
            imt_objs = process_result[imt]
            for obj in imt_objs:
                mag, dist, vs30, ylabel = obj['magnitude'], obj['distance'], \
                                          obj['vs30'], obj['ylabel']
                for gsim, values in obj['yvalues'].items():
                    yield chain([imt, gsim, mag, dist, vs30, ylabel], values)
        # print standard deviations. Do it once for all at the end as we think
        # it might be easier for a user using Excel or LibreOffice, than having
        # each gsim with 'yvalues and 'stdvalues' next to each other
        for imt in process_result['imts']:
            imt_objs = process_result[imt]
            for obj in imt_objs:
                mag, dist, vs30, ylabel = obj['magnitude'], obj['distance'], \
                                          obj['vs30'], obj['stdlabel']
                for gsim, values in obj['stdvalues'].items():
                    # the dict we are iterating might be empty: in case
                    # do not print anything
                    yield chain([imt, gsim, mag, dist, vs30, ylabel], values)

    @classmethod
    def process_data(cls, cleaned_data: dict) -> dict:
        """Process the input data `cleaned_data` returning the response data
        of this form upon user request.
        This method is called by `self.response_data` only if the form is valid.

        :param cleaned_data: the result of `self.cleaned_data`
        """
        params = cleaned_data  # fixme: legacy code, remove and rename?

        # NOTE: the `params` dict will be passed to smtk routines: we use 'pop'
        # whenever possible to avoid passing unwanted params:
        gsim = params.pop("gsim")
        # imt might be None for "spectra" Trellis classes, thus provide None:
        imt = params.pop("imt", None)
        mag_s, dist_s = "magnitude", "distance"
        magnitudes = np.asarray(vectorize(params.pop(mag_s)))  # smtk wants np arrays
        distances = np.asarray(vectorize(params.pop(dist_s)))  # smtk wants np arrays

        plottype_key = params.pop("plot_type")
        trellisclass = PLOT_TYPE[plottype_key][1]
        # define stddev trellis class if the parameter stdev is true
        stdev_trellisclass = None  # do not compute stdev (default)
        if params.pop("stdev", False):
            stdev_trellisclass = PLOT_TYPE[plottype_key][2]

        # Returns True if trellisclass is a Distance-based Trellis class:
        _isdist = trellisclass in (DistanceIMTTrellis, DistanceSigmaIMTTrellis)
        # Returns True if trellisclass is a Magnitude-based Trellis class:
        _ismag = trellisclass in (MagnitudeIMTTrellis, MagnitudeSigmaIMTTrellis)

        xdata = None
        vs30_s, z1pt0_s, z2pt5_s = "vs30", "z1pt0", "z2pt5"
        figures = defaultdict(list)  # imt name -> list of dicts (1 dict=1 plot)
        for vs30, z1pt0, z2pt5 in zip(vectorize(params.pop(vs30_s)),
                                      vectorize(params.pop(z1pt0_s)),
                                      vectorize(params.pop(z2pt5_s))):
            params[vs30_s] = vs30
            params[z1pt0_s] = z1pt0
            params[z2pt5_s] = z2pt5
            # Depending on `trellisclass` we might need to iterate over
            # `magnitudes`, or use `magnitudes` once (the same holds for
            # `distances`). In order to make code cleaner we define a magnitude
            # iterator which yields a two element tuple (m1, m2) where m1 is the
            # scalar value to be saved as json, and m2 is the value
            # (scalar or array) to be passed to the Trellis class:
            for mag, mags in zip(magnitudes, magnitudes) \
                    if _isdist else zip([None], [magnitudes]):
                # same as magnitudes (see above):
                for dist, dists in zip(distances, distances) \
                        if _ismag else zip([None], [distances]):

                    data = cls._get_trellis_dict(trellisclass, params, mags,
                                                  dists, gsim, imt)

                    if xdata is None:
                        xdata = {
                            'xlabel': relabel_sa(data['xlabel']),
                            'xvalues': data['xvalues']
                        }

                    _stdev_data = None if stdev_trellisclass is None \
                        else cls._get_trellis_dict(stdev_trellisclass, params,
                                                    mags, dists, gsim, imt)
                    cls._add_stdev(data, _stdev_data)

                    for fig in data['figures']:
                        # 'fig' represents a plot. It is a dict of this type:
                        # (see method `_get_trellis_dict` and `_add_stdev` above):
                        #    {
                        #        ylabel: str
                        #        stdvalues: {} or dict gsimname -> list of numbers
                        #        stdlabel: str (might be empty str)
                        #        imt: str (the imt)
                        #        yvalues: dict (gsim name -> list of numbers)
                        #    }
                        # Add some keys to 'fig' (magnitude, distance, vs30):
                        # convert to None/float to make them json serializable:
                        for key, val in {vs30_s: vs30,
                                         mag_s: fig.get(mag_s, mag),
                                         dist_s: fig.get(dist_s, dist)}:
                            fig[key] = None if val is None or np.isnan(val) \
                                else float(val)
                        # And add `fig` to `figures`, which is a dict of this type:
                        #    {
                        #        <imt:str>: [<plot:dict>, ..., <plot:ditc>],
                        #        ...
                        #        <imt:str>: [<plot:dict>, ..., <plot:ditc>],
                        #    }
                        # (The plot-dicts count mapped to each imt will depend on
                        # the product of the chosen vs30, mag and dist):
                        figures[fig.pop('imt')].append(fig)

        # imt is a list of the imts given as input, or None for "spectra" Trellis
        # (in this latter case just get the figures keys, which should be populated
        # of a single key 'SA')
        return {
            **xdata,
            'imts': imt or list(figures.keys()),
            **figures
        }

    @staticmethod
    def _get_trellis_dict(trellis_class, params, mags, dists, gsim, imt):  # noqa
        """Compute the Trellis plot for a single set of eGSIM parameters"""

        isspectra = trellis_class in (MagnitudeDistanceSpectraTrellis,
                                      MagnitudeDistanceSpectraSigmaTrellis)

        periods = TrellisForm._default_periods_for_spectra() if isspectra else imt

        trellis_obj = trellis_class.from_rupture_properties(params, mags, dists,
                                                            gsim, periods)
        data = trellis_obj.to_dict()
        # NOTE:
        # data = {
        #    xlabel: str
        #    xvalues: numeric_list
        #    figures: [
        #        {
        #            ylabel: str
        #            row: ? (will be removed)
        #            column: ? (will be removed)
        #            imt: str,
        #            yvalues: {
        #                gsim1 : numeric_list,
        #                ...
        #                gsimN: numeric_list
        #            }
        #        },
        #        ...
        #    ]
        # }

        # We want to get each `figure` element to be a dict of this type:
        #    {
        #        ylabel: str (same as above, but delete trailing zeroes in IMT)
        #        _key: tuple, str (depends on context): unique hashable id
        #        imt: str (the imt)
        #        yvalues: dict (same as above)
        #    }

        src_figures = data['figures']
        for fig in src_figures:
            fig.pop('column', None)
            fig.pop('row', None)
            # set a key to uniquely identify the figure: in case os spectra,
            # we trust the (magnitude, distance) pair. Otherwise, the IMT:
            fig['_key'] = (fig['magnitude'], fig['distance']) if isspectra else \
                fig['imt']
            # change labels SA(1.0000) into SA(1.0)
            fig['ylabel'] = relabel_sa(fig['ylabel'])

        return data

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

    @staticmethod
    def _add_stdev(data, stdev_data=None):
        """Add to each element of data the standard deviations of
        stdev_data.

        :param data: the retuend value of `_get_trellis_dict`, called for a
            given trellis class (no standard deviation)
        :param data: the retuend value of `_get_trellis_dict`, called for the
            appropriate trellis standard deviation class
        """
        if stdev_data is not None:
            # convert the list to a dict with keys the imt
            # (each list element is mapped to a specified imt so this
            # is safe):
            stdev_data['figures'] = {_['_key']: _
                                     for _ in stdev_data['figures']}

        for fig in data['figures']:
            # 'fig' is a dict of this type:
            # (see method `_get_trellis_dict`):
            #    {
            #        ylabel: str
            #        _key: hashable id (tuple, str...)
            #        imt: str (the imt)
            #        yvalues: dict (gsim name -> list of numbers)
            #    }
            fig['stdvalues'] = {}
            fig['stdlabel'] = ''
            # 2. Remove the key '_key' but store it as we might need it
            fig_key = fig.pop('_key')
            # 3. Add standard deviations, if computed (using 'fig_key')
            if stdev_data is not None:
                std_fig = stdev_data['figures'].get(fig_key, {})
                # ('std_fig' is of the same typ of 'fig')
                # Add to 'fig' the 'std_fig' values of interest
                # (renaming them):
                fig['stdvalues'] = std_fig.get('yvalues', {})
                fig['stdlabel'] = std_fig.get('ylabel', '')
