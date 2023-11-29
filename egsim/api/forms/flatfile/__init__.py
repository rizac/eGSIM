"""
Base Form for to model-to-data operations i.e. flatfile handling
"""
from typing import Iterable, Sequence

import pandas as pd
from django.core.exceptions import ValidationError
from django.forms import Form, ModelChoiceField
from django.forms.fields import CharField, FileField

from egsim.smtk import (ground_motion_properties_required_by,
                        intensity_measures_defined_for, registered_imts)
from egsim.smtk.flatfile import (read_flatfile, ColumnDtype,
                                 query as flatfile_query,
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
    # FIXME: centralize the way we fetch data with hidden=False
    flatfile = ModelChoiceField(queryset=models.Flatfile.objects.filter(hidden=False).
                                only('name', 'media_root_path'),
                                to_field_name="name", label='Flatfile',
                                required=False)
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
            dataframe = self.read_flatfile_from_db(cleaned_data["flatfile"])
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
            f_col = flatfile[col]
            if isinstance(f_col.dtype, pd.CategoricalDtype):
                col_dtype = "categorical"
            else:
                col_dtype = ColumnDtype.of(f_col) or "undefined"
            dtypes[col] = col_dtype
        return dtypes


def get_gsims_from_flatfile(flatfile_columns: Sequence[str]) -> Iterable[str]:
    """Yield the GSIM names supported by the given flatfile"""
    ff_cols = set('SA' if _.startswith('SA(') else _ for _ in flatfile_columns)
    imt_cols = ff_cols & set(registered_imts)
    ff_cols -= imt_cols
    for name in models.Gsim.objects.filter(hidden=False).\
            only('name').values_list('name', flat=True):
        imts = intensity_measures_defined_for(name)
        if not imts.intersection(imt_cols):
            continue
        if all(get_all_names_of(p) & ff_cols
               for p in ground_motion_properties_required_by(name)):
            yield name
