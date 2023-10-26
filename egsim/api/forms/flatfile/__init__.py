"""
Base Form for to model-to-data operations i.e. flatfile handling
"""
from collections import defaultdict
from datetime import datetime
from typing import Iterable, Sequence

import pandas as pd
from django.core.exceptions import ValidationError
from django.forms import Form, ModelChoiceField
from django.forms.fields import CharField, FileField

from egsim.smtk import (registered_gsims, ground_motion_properties_required_by,
                        imts_defined_for)
from egsim.smtk.flatfile import (read_flatfile, ColumnDtype, query as flatfile_query,
                                 get_all_names_of)
from egsim.api import models
from egsim.api.forms import EgsimBaseForm


# Let's provide uploaded flatfile Field in a separate Form as the Field is not
# strictly JSON-encodable (info here: https://stackoverflow.com/a/4083908) and
# should be kept private/hidden by default:
class _UploadedFlatfile(Form):
    flatfile = FileField(required=False)  # keep same name as flatfile below


class FlatfileForm(EgsimBaseForm):
    """Base Form for handling Flatfiles"""

    # Custom API param names (see doc of `EgsimBaseForm._field2params` for details):
    _field2params = {
        'selexpr': ['data-query', 'selection-expression']
    }

    flatfile = ModelChoiceField(queryset=models.Flatfile.objects,
                                to_field_name="name", label='Flatfile',
                                empty_label=None, required=False)
    selexpr = CharField(required=False, label='Filter flatfile records via a '
                                              'query string')

    def __init__(self, data, files=None, **kwargs):
        # set now `self._u_ff`, in case `self.clean` is called in `super.__init__` below:
        self._u_ff = None if files is None else _UploadedFlatfile(files=files)
        super().__init__(data=data, **kwargs)

    def clean(self):
        """Call `super.clean()` and handle the flatfile"""
        u_form = self._u_ff

        # Handle flatfiles conflicts first. Note: with no selection from the web GUI we
        # have data['flatfile'] = None
        if u_form is not None and self.data.get('flatfile', None):
            self.add_error("flatfile", ValidationError('Please either select a '
                                                       'flatfile, or upload one',
                                                       code='conflict'))
        elif u_form is None and not self.data.get('flatfile', None):
            # note: with no selection from the web GUI we have data['flatfile'] = None
            self.add_error("flatfile",  ValidationError('Please select a flatfile '
                                                        'or upload one',
                                                        code='required'))

        cleaned_data = super().clean()

        if self.has_error('flatfile'):
            return cleaned_data

        u_flatfile = None  # None or bytes object

        if u_form is not None:
            if not u_form.is_valid():
                self._errors = u_form._errors
                return cleaned_data
            # the files dict[str, UploadedFile] should have only one item
            # in any case, get the first value:
            u_flatfile = u_form.files[next(iter(u_form.files))]  # Django Uploaded file
            u_flatfile = u_flatfile.file  # ByesIO or similar

        if u_flatfile is None:
            # exception should be raised and sent as 500: don't catch
            p_ff = cleaned_data["flatfile"]
            if p_ff.expiration is not None and p_ff.expiration > datetime.utcnow():
                self.add_error("flatfile", ValidationError("Flatfile expired",
                                                           code='invalid'))
                return cleaned_data  # no nned to further process
            dataframe = self.read_flatfile_from_db(p_ff)
        else:
            # u_ff = cleaned_data[key_u]
            try:
                # u_flatfile is a Django TemporaryUploadedFile or InMemoryUploadedFile
                # (the former if file size > configurable threshold
                # (https://stackoverflow.com/a/10758350):
                dataframe = self.read_flatfilefrom_csv_bytes(u_flatfile)
            except Exception as exc:
                msg = str(exc)
                # Use 'flatfile' as error key: users can not be confused
                # (see __init__), and also 'flatfile' is also the exposed key
                # for the `files` argument in requests
                self.add_error("flatfile", ValidationError(msg, code='invalid'))
                return cleaned_data  # no need to further process

        # replace the flatfile parameter with the pandas dataframe:
        cleaned_data['flatfile'] = dataframe

        key = 'selexpr'
        selexpr = cleaned_data.get(key, None)
        if selexpr:
            try:
                cleaned_data['flatfile'] = flatfile_query(dataframe, selexpr).copy()
            except Exception as exc:
                # add_error removes also the field from self.cleaned_data:
                self.add_error(key, ValidationError(str(exc), code='invalid'))

        return cleaned_data

    @classmethod
    def read_flatfile_from_db(cls, model_instance: models.Flatfile) -> pd.DataFrame:
        return pd.read_hdf(model_instance.filepath, key=model_instance.name)  # noqa

    @classmethod
    def read_flatfilefrom_csv_bytes(cls, buffer, *, sep=None) -> pd.DataFrame:
        return read_flatfile(buffer, sep=sep)

    @classmethod
    def get_flatfile_dtypes(cls, flatfile: pd.DataFrame) -> dict[str, str]:
        """Return the human-readable data type description for each column of the given
        flatfile
        """
        dtypes = {}
        for col in flatfile.columns:
            dtype_name = 'unknown'
            if isinstance(col.dtype, pd.CategoricalDtype):
                dtype_name = "categorical data"
            else:
                col_dtype = ColumnDtype.of(flatfile[col])
                if col_dtype is not None:
                    dtype_name = col_dtype.name
            dtypes[col] = dtype_name
        return dtypes


def get_gsims_from_flatfile(flatfile_columns: Sequence[str]) -> Iterable[str]:
    """Yield the GSIM names supported by the given flatfile"""
    ff_cols = set('SA' if _.startswith('SA(') else _ for _ in flatfile_columns)
    for name, model_cls in registered_gsims.items():
        imts = imts_defined_for(model_cls)
        if not imts.intersection(ff_cols):
            continue
        for gm_prop in ground_motion_properties_required_by(model_cls):
            if not get_all_names_of(gm_prop) & ff_cols:
                continue
        yield name

    # FIXME: REMOVE
    # model2cols = defaultdict(set)
    # # filter models by imts (feasible via SQL) and build a dict of models with the
    # # relatvie required flatfile columns (filter donw below, not possible to do in SQL):
    # for model_name, required_fcol in models.Gsim.objects.filter(imts__name__in=ff_cols).\
    #         values_list('name', 'required_flatfile_columns__name'):
    #     model2cols[model_name].add(required_fcol)
    # # filter on required flatfile columns and yields supported models:
    # for model_name, cols in model2cols.items():
    #     if not cols - ff_cols:
    #         yield model_name
