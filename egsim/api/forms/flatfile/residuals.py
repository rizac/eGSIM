"""
Django Forms for eGSIM model-to-data comparison (residuals computation)

@author: riccardo
"""
import pandas as pd

from egsim.smtk import get_residuals
from egsim.api.forms import APIForm
from egsim.api.forms import GsimImtForm
from egsim.api.forms.flatfile import FlatfileForm, get_gsims_from_flatfile


class ResidualsForm(GsimImtForm, FlatfileForm, APIForm):
    """Form for residual analysis"""

    # Custom API param names (see doc of `EgsimBaseForm._field2params` for details):
    _field2params = {}

    def clean(self):
        cleaned_data = super().clean()
        if not self.has_error('flatfile'):
            flatfile = cleaned_data['flatfile']
            if 'gsim' in cleaned_data:
                invalid_gsims = set(cleaned_data['gsim']) - \
                                set(get_gsims_from_flatfile(flatfile.columns))
                if invalid_gsims:
                    # put sorted list of models to facilitate tests:
                    self.add_error('flatfile', f'missing columns required by '
                                               f'{", ".join(sorted(invalid_gsims))}')
                    return cleaned_data

        return cleaned_data

    def response_data(self) -> pd.DataFrame:
        cleaned_data = self.cleaned_data
        return get_residuals(cleaned_data["gsim"],
                             cleaned_data["imt"],
                             cleaned_data['flatfile'])
