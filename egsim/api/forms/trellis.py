"""
Django Forms for eGSIM model-to-model comparison (Trellis plots)
"""
from collections import defaultdict
from itertools import chain, repeat
from typing import Iterable, Any

import numpy as np
from openquake.hazardlib import imt
from openquake.hazardlib.geo import Point
from openquake.hazardlib.scalerel import get_available_magnitude_scalerel
from ...smtk.trellis.configure import vs30_to_z1pt0_cy14, vs30_to_z2pt5_cb14
from ...smtk.trellis.trellis_plots import (DistanceIMTTrellis,
                                           MagnitudeIMTTrellis,
                                           DistanceSigmaIMTTrellis,
                                           MagnitudeSigmaIMTTrellis,
                                           MagnitudeDistanceSpectraTrellis,
                                           MagnitudeDistanceSpectraSigmaTrellis)
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.forms.fields import BooleanField, FloatField, ChoiceField

from egsim.api.forms import APIForm, GsimImtForm, relabel_sa
from egsim.api.forms.fields import NArrayField, vectorize, isscalar


PLOT_TYPE = {
    # key: (display label, trellis class, stddev trellis class)
    'd': ('IMT vs. Distance', DistanceIMTTrellis, DistanceSigmaIMTTrellis),
    'm': ('IMT vs. Magnitude', MagnitudeIMTTrellis, MagnitudeSigmaIMTTrellis),
    's': ('Magnitude-Distance Spectra', MagnitudeDistanceSpectraTrellis,
          MagnitudeDistanceSpectraSigmaTrellis)
}

_mag_scalerel = get_available_magnitude_scalerel()


class TrellisForm(GsimImtForm, APIForm):
    """Form for Trellis plot generation"""

    # Custom API param names (see doc of `EgsimBaseForm._field2params` for details):
    _field2params = {
        'plot_type': ['plot'],
        'stdev': ['stdev', 'stddev'],
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

    plot_type = ChoiceField(label='Plot type',
                            choices=[(k, f'{v[0]} [{k}]')
                                     for k, v in PLOT_TYPE.items()])
    stdev = BooleanField(label='Compute Standard Deviation(s)', required=False,
                         initial=False)

    # GSIM RUPTURE PARAMS:
    magnitude = NArrayField(label='Magnitude(s)', min_count=1)
    distance = NArrayField(label='Distance(s)', min_count=1)
    vs30 = NArrayField(label=mark_safe('V<sub>S30</sub> (m/s)'),
                       min_value=0., min_count=1, initial=760.0)
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
    initial_point = NArrayField(label="Location on Earth", min_count=2, max_count=2,
                                help_text='Longitude Latitude', initial="0 0",
                                min_value=[-180, -90], max_value=[180, 90])
    hypocentre_location = NArrayField(label="Location of Hypocentre",
                                      initial='0.5 0.5',
                                      help_text='Along-strike fraction, '
                                                'Down-dip fraction',
                                      min_count=2, max_count=2, min_value=[0, 0],
                                      max_value=[1, 1])
    # END OF RUPTURE PARAMS
    vs30measured = BooleanField(label=mark_safe('V<sub>S30</sub> is measured'),
                                help_text='Otherwise is inferred',
                                initial=True, required=False)
    line_azimuth = FloatField(label='Azimuth of Comparison Line',
                              min_value=0., max_value=360., initial=0.)
    z1pt0 = NArrayField(label=mark_safe('Depth to 1 km/s V<sub>S</sub> layer (m)'),
                        min_value=0., required=False,
                        help_text=mark_safe("Calculated from the "
                                            "V<sub>S30</sub> if not given"))
    z2pt5 = NArrayField(label=mark_safe('Depth to 2.5 km/s V<sub>S</sub> layer (km)'),
                        min_value=0., required=False,
                        help_text=mark_safe("Calculated from the  "
                                            "V<sub>S30</sub> if not given"))
    backarc = BooleanField(label='Backarc Path', initial=False,
                           required=False)

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

    def clean_imt(self):
        """Clean the imt Field by checking that it is empty or composed of SA only,
        in cae the magnitude-speactra plots are requested"""
        imts = self.cleaned_data.get('imt', [])
        if self._is_input_plottype_spectra():
            # check invalid IMTs:
            invalid_imts = [_ for _ in imts if not _.startswith('SA')]
            if invalid_imts:
                raise ValidationError(f'Invalid value(s): {", ".join(invalid_imts)}. '
                                      f'Omit this parameter or provide a '
                                      f'custom list of SA periods when selecting '
                                      f'"spectra" plots',
                                      code='invalid')
            # If no SA is found (with or without period) add "SA": this will not be used
            # in `self.clean` below but in `GsimImtForm.clean()` to check that the models
            # provided are compatible with SA
            if not any(_.startswith('SA') for _ in imts):
                return list(imts) + ['SA']
        return imts

    def _is_input_plottype_spectra(self):
        return self.data.get('plot_type', '') in ('s', 'ss')

    def clean(self):
        cleaned_data = super().clean()

        if self._is_input_plottype_spectra():
            # cleaned_data['imt'] is either [] or a list of 'SA', with or without period.
            # Extract periods cause the trellis code expects 'imt' as float in this case:
            periods = sorted(imt.from_string(_).period
                             for _ in cleaned_data.get('imt', [])
                             if _ != 'SA')
            if not periods:
                # provide default periods if none found:
                periods = self._default_periods_for_spectra()
            # set the correct value:
            cleaned_data['imt'] = periods

        # calculate z1pt0 and z2pt5 if needed, raise in case of errors:
        vs30 = cleaned_data['vs30']  # surely a list with st least one element
        vs30scalar = isscalar(vs30)
        vs30s = np.array(vectorize(vs30), dtype=float)

        # check vs30-dependent values:
        for name, func in (['z1pt0', vs30_to_z1pt0_cy14],
                           ['z2pt5', vs30_to_z2pt5_cb14]):
            if cleaned_data.get(name, None) in (None, []):
                values = func(vs30s)  # numpy-function
                cleaned_data[name] = \
                    float(values[0]) if vs30scalar else values.tolist()
            elif isscalar(cleaned_data[name]) != isscalar(vs30) or \
                    (not isscalar(vs30) and
                     len(vs30) != len(cleaned_data[name])):
                str_ = 'scalar' if isscalar(vs30) else \
                    '%d-elements vector' % len(vs30)
                # add error for vs30 param:
                error = ValidationError(f"value must be consistent with vs30 ({str_})",
                                        code='invalid')
                self.add_error(name, error)

        return cleaned_data

    @classmethod
    def csv_rows(cls, processed_data) -> Iterable[Iterable[Any]]:
        """Yield CSV rows, where each row is an iterables of Python objects
        representing a cell value. Each row doesn't need to contain the same
        number of elements, the caller function `self.to_csv_buffer` will pad
        columns with Nones, in case (note that None is rendered as "", any other
        value using its string representation).

        :param processed_data: dict resulting from `self.process_data`
        """
        mag_s, dist_s = 'magnitude', 'distance'
        yield ['imt', 'model', f'{mag_s}', f'{dist_s}', 'vs30']
        yield chain(repeat('', 5), [processed_data['xlabel']],
                    processed_data['xvalues'])
        for imt in processed_data['imts']:
            imt_objs = processed_data[imt]
            for obj in imt_objs:
                mag, dist, vs30, ylabel = obj[mag_s], obj[dist_s], \
                                          obj['vs30'], obj['ylabel']
                for gsim, values in obj['yvalues'].items():
                    yield chain([imt, gsim, mag, dist, vs30, ylabel], values)
        # print standard deviations. Do it once for all at the end as we think
        # it might be easier for a user using Excel or LibreOffice, than having
        # each gsim with 'yvalues and 'stdvalues' next to each other
        for imt in processed_data['imts']:
            imt_objs = processed_data[imt]
            for obj in imt_objs:
                mag, dist, vs30, ylabel = obj[mag_s], obj[dist_s], \
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
        # get magnitudes and distances (smtk wants np arrays):
        magnitudes = np.asarray(vectorize(params.pop("magnitude")))
        distances = np.asarray(vectorize(params.pop("distance")))
        # Set labels for mag and dist shown in *outputs dictionaries* :
        mag_s, dist_s = "magnitude", "distance"

        plottype_key = params.pop("plot_type")
        trellisclass = PLOT_TYPE[plottype_key][1]
        # define stddev trellis class if the parameter stdev is true
        stdev_trellisclass = None  # do not compute stdev (default)
        if params.pop("stdev", False):
            stdev_trellisclass = PLOT_TYPE[plottype_key][2]

        is_spectra_class = trellisclass in (MagnitudeDistanceSpectraTrellis,
                                            MagnitudeDistanceSpectraSigmaTrellis)
        _isdist, _ismag = False, False
        if not is_spectra_class:
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
                                                 dists, gsim, imt,
                                                 is_spectra_class)

                    if xdata is None:
                        xdata = {
                            'xlabel': relabel_sa(data['xlabel']),
                            'xvalues': data['xvalues']
                        }

                    _stdev_data = None if stdev_trellisclass is None \
                        else cls._get_trellis_dict(stdev_trellisclass, params,
                                                   mags, dists, gsim, imt,
                                                   is_spectra_class)
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
                                         dist_s: fig.get(dist_s, dist)}.items():
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

        return {
            **xdata,
            # imt is a list of the imts given as input, or a numeric list of periods
            # for "spectra" Trellis (in the latter case just get the figures keys,
            # which should be populated of a single key 'SA'):
            'imts': imt if not is_spectra_class else list(figures.keys()),
            **figures
        }

    @staticmethod
    def _get_trellis_dict(trellis_class, params, mags, dists, gsim, imt,
                          is_trelliclass_spectra):  # noqa
        """Compute the Trellis plot for a single set of eGSIM parameters"""

        # imt is a list of the imts given as input, or a numeric list of periods
        # for "spectra" Trellis (in the latter case just get the figures keys,
        # which should be populated of a single key 'SA'):
        trellis_obj = trellis_class.from_rupture_properties(params, mags, dists,
                                                            gsim, imt)
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
            # set a key to uniquely identify the figure (see `process_data`).
            # Use the IMT except for trellis spectra, where imt is always SA:
            # use (mag, dist) pair in this case:
            fig['_key'] = (fig['magnitude'], fig['distance']) \
                if is_trelliclass_spectra else fig['imt']
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
