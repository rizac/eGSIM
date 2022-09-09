"""
Django Forms for eGSIM model-to-data testing

@author: riccardo
"""
from collections import defaultdict
from typing import Iterable, Any

import numpy as np
from django.core.exceptions import ValidationError

from smtk.residuals.gmpe_residuals import GSIM_MODEL_DATA_TESTS as TEST

from . import MOF, get_residuals, GsimImtFlatfileForm
from .. import APIForm, relabel_sa
from ..fields import MultipleChoiceField, FloatField


MOF_TYPE = {
    # key -> display name, test_function(residuals, config)
    MOF.RES: ('Residuals', TEST['Residuals']),
    MOF.LH: ("Likelihood", TEST["Likelihood"]),
    MOF.LLH: ("Log-Likelihood", TEST["LLH"]),
    MOF.MLLH: ("Multivariate Log-Likelihood", TEST["MultivariateLLH"]),
    MOF.EDR: ("Euclidean Distance-Based Ranking", TEST["EDR"])
}


class TestingForm(GsimImtFlatfileForm, APIForm):
    """Form for testing Gsims via Measures of Fit"""

    # Set the public names of this Form Fields as `public_name: attribute_name`
    # mappings. Superclass mappings are merged into this one. An attribute name
    # can be keyed by several names, and will be keyed by itself anyway if not
    # done here (see `egsim.forms.EgsimFormMeta` for details)
    public_field_names = {
        'mof': 'fit_measure', 'measure_of_fit': 'fit_measure'
    }

    fit_measure = MultipleChoiceField(required=True, label="Measure(s) of fit",
                                      choices=[(k, f'{v[0]} [{k}]')
                                               for k, v in MOF_TYPE.items()])
    edr_bandwidth = FloatField(required=False, initial=0.01, label="EDR bandwith",
                               help_text='Ignored if the measure of fit is not EDR')
    edr_multiplier = FloatField(required=False, initial=3.0,  label="EDR multiplier",
                                help_text='Ignored if the measure of fit is not EDR')

    def clean(self):
        cleaned_data = super().clean()
        config = {}
        for parname in ['edr_bandwidth', 'edr_multiplier']:
            if parname in cleaned_data:
                config[parname] = cleaned_data[parname]
        cleaned_data['config'] = config
        return cleaned_data

    @classmethod
    def process_data(cls, cleaned_data: dict) -> dict:
        """Process the input data `cleaned_data` returning the response data
        of this form upon user request.
        This method is called by `self.response_data` only if the form is valid.

        :param cleaned_data: the result of `self.cleaned_data`
        """

        params = cleaned_data  # FIXME: legacy code, remove/rename?

        flatfile = params['flatfile']  # already filtered dataframe, in case

        ret = {}
        obs_count = defaultdict(int)
        gsim_skipped = {}
        config = params.get('config', {})
        # columns: "Measure of fit" "imt" "gsim" "value(s)"
        for gsim in params['gsim']:
            try:
                residuals = get_residuals(flatfile, [gsim], params['imt'])

                numrecords = sum(c.get('Num. Sites', 0) for c in residuals.contexts)

                obs_count[gsim] = numrecords
                if not numrecords:
                    gsim_skipped[gsim] = 'No matching db record found'
                    continue

                gsim_values = []

                for key in params["fit_measure"]:
                    name, func = MOF_TYPE[key]
                    result = func(residuals, config)
                    gsim_values.extend(_itervalues(gsim, key, name, result))

                for moffit, imt, value in gsim_values:
                    # note: value isa Numpy scalar, but not ALL numpy scalar
                    # are json serializable: only those that are equal to Python's
                    ret.setdefault(moffit, {}). \
                        setdefault(imt, {})[gsim] = value.item()

            except ValidationError as verr:
                # this exception must be raised and wrapped into a 4xx response:
                raise verr
            except Exception as exc:  # pylint: disable=broad-except
                gsim_skipped[gsim] = str(exc)

        return {
            'Measure of fit': ret,
            'Db records': obs_count,
            'Gsim skipped': gsim_skipped
        }

    @classmethod
    def csv_rows(cls, processed_data: dict) -> Iterable[Iterable[Any]]:
        """Yield CSV rows, where each row is an iterables of Python objects
        representing a cell value. Each row doesn't need to contain the same
        number of elements, the caller function `self.to_csv_buffer` will pad
        columns with Nones, in case (note that None is rendered as "", any other
        value using its string representation).

        :param processed_data: dict resulting from `self.process_data`
        """
        fitmeasures = processed_data['Measure of fit']
        dbrecords = processed_data['Db records']
        yield ['measure of fit', 'imt', 'gsim', 'value', 'db records used']
        for mof, mofs in fitmeasures.items():
            for imt, imts in mofs.items():
                for gsim, value in imts.items():
                    yield [mof, imt, gsim, value, dbrecords[gsim]]


####################################################
# Private functions needed from process_data above #
####################################################


def _itervalues(gsim, key, name, result):
    """Yield the tuples
        (Measure of fit, IMT, value)
    (str, str, numeric) by parsing `result`

    :param key: the key denoting a measure of fit
    :param name: a name denoting the measure of fit
    :param result: the result of the smtk computation of the given measure of
        fit on the given gsim
    """

    if isinstance(result, (list, tuple)):
        result = result[0]
    # Returned object are of this type (<GMPE>: any valid Gmpe as string,
    # <IMT>: any valid IMT as string, <TYPE>: str in "Total", "Inter event"
    # or "Intra event". <EDRTYPE>: string in "MDE Norm", "sqrt Kappa" or
    # "EDR"):
    #
    # Residuals:
    # {
    #   <GMPE>: {
    #      <IMT>: {
    #        <TYPE>: {
    #            "Mean": <float>,
    #            "Std Dev": <float>
    #        }
    #      }
    #   }
    # }
    #
    # Likelihood:
    # {
    #   <GMPE>: {
    #      <IMT>: {
    #        <TYPE>: <ndarray>
    #        }
    #      }
    #   }
    # }
    #
    # Log-Likelihood, Multivariate Log-Likelihood:
    # {
    #   <GMPE>: {
    #      <IMT>: <float>  # IMT includes the "All" key
    #   }
    # }
    #
    # EDR
    # {
    #   <GMPE>: {
    #      <EDRTYPE>: <float>
    #   }
    # }
    #
    # The code belows re-arranges the dicts flattening them like this:
    # "<Residual name> <residual type if any>":{
    #        <IMT>: {
    #           <GMPE>: float or ndarray
    #        }
    #     }
    # }

    gsim_result = result[gsim]
    if key == MOF.RES:
        for imt, imt_result in gsim_result.items():
            imt2 = relabel_sa(imt)
            for type_, type_result in imt_result.items():
                for meas, value in type_result.items():
                    moffit = "%s %s %s" % (name, type_, meas)
                    yield _title(moffit), imt2, value
    elif key == MOF.LH:
        for imt, imt_result in gsim_result.items():
            imt2 = relabel_sa(imt)
            for type_, values in imt_result.items():
                # change array value into Median and IQR:
                p25, p50, p75 = np.nanpercentile(values, [25, 50, 75])
                for kkk, vvv in (('Median', p50), ('IQR', p75 - p25)):
                    moffit = "%s %s %s" % (name, type_, kkk)
                    yield _title(moffit), imt2, vvv
    elif key in (MOF.LLH, MOF.MLLH):
        for imt, value in gsim_result.items():
            imt2 = relabel_sa(imt)
            moffit = name
            yield _title(moffit), imt2, value
    elif key == MOF.EDR:
        for type_, value in gsim_result.items():
            moffit = "%s %s" % (name, type_)
            imt = ""  # hack
            yield _title(moffit), imt, value


def _title(string):
    """Make the string with the first letter of the first word capitalized
    only and replaces 'std dev' with 'stddev' for consistency with
    residuals
    """
    return (string[:1].upper() + string[1:].lower()).replace('std dev',
                                                             'stddev')
