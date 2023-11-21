"""
Django Forms for eGSIM model-to-data comparison (residuals computation)

@author: riccardo
"""
import pandas as pd
from django.core.exceptions import ValidationError

from egsim.smtk import get_residuals
from egsim.api.forms import APIForm
from egsim.api.forms import GsimImtForm
from egsim.api.forms.flatfile import FlatfileForm, get_gsims_from_flatfile
from egsim.smtk.converters import dataframe2dict


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
                    inv_str = ', '.join(sorted(invalid_gsims)[:5])
                    if len(invalid_gsims) > 5:
                        inv_str += ' ... (showing first 5 only)'
                    err_gsim = ValidationError(f"{len(invalid_gsims)} model(s) not "
                                               f"supported by the given flatfile: "
                                               f"{inv_str}", code='invalid')
                    # add_error removes also the field from self.cleaned_data:
                    self.add_error('gsim', err_gsim)
                    cleaned_data.pop('flatfile')
                    return cleaned_data

        return cleaned_data

    @classmethod
    def response_data(cls, cleaned_data: dict) -> pd.DataFrame:
        return get_residuals(cleaned_data["gsim"],
                             cleaned_data["imt"],
                             cleaned_data['flatfile'])
