"""
Django Forms for eGSIM model-to-data comparison (residuals computation)

@author: riccardo
"""
import pandas as pd
from django.forms import BooleanField

from egsim.smtk import get_residuals, FlatfileError, get_measures_of_fit
from egsim.api.forms import APIForm
from egsim.api.forms import GsimImtForm
from egsim.api.forms.flatfile import FlatfileForm


class ResidualsForm(GsimImtForm, FlatfileForm, APIForm):
    """Form for residual analysis"""

    likelihood = BooleanField(initial=False, required=False,
                              help_text='compute the residuals likelihood '
                                        '(Scherbaum et al. 2004. '
                                        'https://doi.org/10.1785/0120030147)')
    normalize = BooleanField(initial=True, required=False,
                             help_text=('normalize the random effects residuals '
                                        '(Abrahamson & Youngs (1992), Eq. 10)'))
    ranking = BooleanField(initial=False, required=False,
                           help_text='Model ranking: easily assess how predictions '
                                     'fit the data by returning aggregate '
                                     'measures from the computed residuals (e.g., '
                                     'median, loglikelihood, EDR). With ranking, '
                                     'the parameters likelihood and normalize are '
                                     'set to true by default')

    # Custom API param names (see doc of `EgsimBaseForm._field2params` for details):
    _field2params = {}

    def output(self) -> pd.DataFrame:
        """Compute and return the output from the input data (`self.cleaned_data`).
        This method must be called after checking that `self.is_valid()` is True.
        On Flatfile errors, return None and add register the error
        (see `self.errors_json_data` for details) so that `self.is_valid=False`.

        :return: any Python object (e.g., a JSON-serializable dict)
        """
        try:
            cleaned_data = self.cleaned_data
            gsims, imts = cleaned_data["gsim"], cleaned_data["imt"]
            is_ranking = cleaned_data['ranking']
            residuals = get_residuals(
                cleaned_data["gsim"],
                cleaned_data["imt"],
                cleaned_data['flatfile'],
                likelihood=True if is_ranking else cleaned_data['likelihood'],
                mean=is_ranking,
                normalise=True if is_ranking else cleaned_data['normalize'])
            if is_ranking:
                return get_measures_of_fit(gsims, imts, residuals)
            return residuals
        except FlatfileError as err:
            self.add_error("flatfile", str(err))

