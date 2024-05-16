"""
Django Forms for eGSIM model-to-data comparison (residuals computation)

@author: riccardo
"""
import pandas as pd
from django.forms import BooleanField
from collections.abc import Collection

from egsim.smtk import get_residuals, intensity_measures_defined_for, \
    ground_motion_properties_required_by
from egsim.api.forms import APIForm
from egsim.api.forms import GsimImtForm
from egsim.api.forms.flatfile import FlatfileForm
from egsim.smtk.flatfile import FlatfileMetadata
from egsim.smtk.validators import sa_period


class ResidualsForm(GsimImtForm, FlatfileForm, APIForm):
    """Form for residual analysis"""

    likelihood = BooleanField(initial=False, required=False,
                              help_text='compute the residuals likelihood '
                                        'according to Scherbaum et al. 2004 '
                                        '(https://doi.org/10.1785/0120030147)')
    # Custom API param names (see doc of `EgsimBaseForm._field2params` for details):
    _field2params = {}

    def clean(self):
        cleaned_data = super().clean()
        if not self.has_error('flatfile') and not self.has_error('gsim'):
            # check missing required columns (this is done also later in smtk.residuals,
            # but we want to quickly return in case of errors). Also note that potential
            # duplicated column names - as well as all flatfile errors that do not
            # depend on the given models - are already checked in the superclass
            miss = self.check_missing_columns(
                cleaned_data['flatfile'].columns, cleaned_data.get('gsim', []))
            if miss:
                self.add_error('flatfile',
                               f'missing required column(s): '
                               f'{", ".join(miss)}')

        return cleaned_data

    @staticmethod
    def check_missing_columns(
            flatfile_columns: Collection[str], models: list[str]) -> list[str]:
        """
        Return a list of column names not present in `flatfile_columns` that should be
        required by the given model(s) in `models`
        """
        errors = set()
        ff_cols = set('SA' if sa_period(f) is not None else f for f in flatfile_columns)
        for name in models:
            imts = intensity_measures_defined_for(name)
            if not imts.intersection(ff_cols):
                errors.add(" or ".join(sorted(imts)))
            for col in ground_motion_properties_required_by(name):
                if not (set(FlatfileMetadata.get_aliases(col)) & ff_cols):
                    errors.add(col)
        return sorted(errors)

    def output(self) -> pd.DataFrame:
        """Compute and return the output from the input data (`self.cleaned_data`).
        This method must be called after checking that `self.is_valid()` is True

        :return: any Python object (e.g., a JSON-serializable dict)
        """
        cleaned_data = self.cleaned_data
        return get_residuals(cleaned_data["gsim"],
                             cleaned_data["imt"],
                             cleaned_data['flatfile'],
                             cleaned_data['likelihood'])
