"""Utilities for flatfile with gsim comparison (residuals, testing)"""
from typing import Sequence

import pandas as pd
from django.core.exceptions import ValidationError

from egsim.smtk.residuals.gmpe_residuals import Residuals
from egsim.smtk.flatfile import ColumnType, ContextDB
from egsim.api import models
from egsim.api.forms import GsimImtForm
from egsim.api.forms.flatfile import FlatfileForm, get_gsims_from_flatfile


class MOF:  # noqa
    # simple class emulating an Enum
    RES = 'res'
    LH = 'l'
    LLH = "ll"
    MLLH = "mll"
    EDR = "edr"


def get_residuals(flatfile: pd.DataFrame, gsim: list[str], imt: list[str]) -> Residuals:
    """Instantiate a Residuals object with computed residuals. Wrap missing
    flatfile columns into a ValidationError so that it can be returned as
    "client error" (4xx) response
    """
    context_db = ContextDB(flatfile)
    residuals = Residuals(gsim, imt)
    residuals.get_residuals(context_db)
    return residuals


class GsimImtFlatfileForm(GsimImtForm, FlatfileForm):
    """Base (abstract-like) Form handling flatfile and models"""

    def clean(self):
        cleaned_data = super().clean()
        if not self.has_error('flatfile'):
            flatfile = cleaned_data['flatfile']
            if 'gsim' in cleaned_data:
                invalid_gsims = \
                    self.get_flatfile_invalid_gsim(flatfile, cleaned_data['gsim'])
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
    def get_flatfile_invalid_gsim(cls, flatfile: pd.DataFrame,
                                  gsims: Sequence[str]) -> set[str, ...]:
        return set(gsims) - set(get_gsims_from_flatfile(flatfile.columns))
