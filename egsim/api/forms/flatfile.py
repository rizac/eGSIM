"""
Base Form for to model-to-data operations i.e. flatfile handling
"""
from typing import Iterable, Sequence, Optional, Any
import pandas as pd

from django.forms import Form
from django.forms.fields import CharField, FileField

from egsim.smtk import (ground_motion_properties_required_by,
                        intensity_measures_defined_for, registered_imts)
from egsim.smtk.flatfile import (read_flatfile, get_dtype_of, FlatfileMetadata,
                                 query as flatfile_query)
from egsim.api import models
from egsim.api.forms import EgsimBaseForm, APIForm, GsimImtForm


# Let's provide uploaded flatfile Field in a separate Form as the Field is not
# strictly JSON-encodable (info here: https://stackoverflow.com/a/4083908) and
# should be kept private/hidden by default:
class _UploadedFlatfile(Form):
    flatfile = FileField(
        required=False,
        allow_empty_file=False,
        error_messages={
            'empty': 'the submitted file is empty'
        }
    )


class FlatfileForm(EgsimBaseForm):
    """Base Form for handling Flatfiles"""

    # Custom API param names (see doc of `EgsimBaseForm._field2params` for details):
    _field2params: dict[str, tuple[str]] = {
        'selexpr': ('flatfile-query', 'data-query', 'selection-expression'),
        'flatfile': ('flatfile', 'data')
    }
    flatfile = CharField(
        required=False,
        help_text="The flatfile (pre- or user-defined) containing observed ground "
                  "motion properties and intensity measures, in CSV or HDF format"
    )  # Note: with a ModelChoiceField the benefits of handling validation are outweighed
    # by the fixes needed here and there to make values JSON serializable, so we opt for
    # a CharField + custom validation in `clean`
    selexpr = CharField(
        required=False,
        help_text='Filter flatfile records (rows) matching query expressions applied '
                  'on the columns, e.g.: "(mag > 6) & (rrup < 10)" (&=and, |=or)'
    )

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
            self.add_error("flatfile", 'select a flatfile by name or upload one, '
                                       'not both')
        elif u_form is None and not self.data.get('flatfile', None):
            # note: with no selection from the web GUI we have data['flatfile'] = None
            self.add_error("flatfile",  self.ErrCode.required)

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

        if u_flatfile is None:  # predefined flatfile
            flatfile_db_obj = models.Flatfile.queryset('name', 'media_root_path').\
                filter(name=cleaned_data['flatfile']).first()
            if flatfile_db_obj is None:
                self.add_error("flatfile", self.ErrCode.invalid_choice)
                return cleaned_data
            # cleaned_data["flatfile"] is a models.Flatfile instance:
            dataframe = flatfile_db_obj.read_from_filepath()
        else:  # uploaded (user-defined) flatfile
            try:
                # u_flatfile is a Django TemporaryUploadedFile or InMemoryUploadedFile
                # (the former if file size > configurable threshold
                # (https://stackoverflow.com/a/10758350):
                dataframe = read_flatfile(u_flatfile)
            except Exception as exc:
                # Use 'flatfile' as error key: users can not be confused
                # (see __init__), and also 'flatfile' is also the exposed key
                # for the `files` argument in requests
                self.add_error("flatfile", str(exc))
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
                self.add_error(key, str(exc))

        return cleaned_data


def get_gsims_from_flatfile(flatfile_columns: Sequence[str]) -> Iterable[str]:
    """Yield the GSIM names supported by the given flatfile"""
    ff_cols = set('SA' if _.startswith('SA(') else _ for _ in flatfile_columns)
    imt_cols = ff_cols & set(registered_imts)
    ff_cols -= imt_cols
    for name in models.Gsim.names():
        imts = intensity_measures_defined_for(name)
        if not imts.intersection(imt_cols):
            continue
        if all(set(FlatfileMetadata.get_aliases(p)) & ff_cols
               for p in ground_motion_properties_required_by(name)):
            yield name


class FlatfileValidationForm(APIForm, FlatfileForm):
    """Form for flatfile validation, on success
    return info from a given uploaded flatfile"""

    def output(self) -> dict:
        """Compute and return the output from the input data (`self.cleaned_data`).
        This method must be called after checking that `self.is_valid()` is True

        :return: any Python object (e.g., a JSON-serializable dict)
        """
        cleaned_data = self.cleaned_data
        dataframe = cleaned_data['flatfile']
        columns = []
        for col in sorted(dataframe.columns):
            # return the flatfile metadata from the column values (pass
            # dataframe[col] as 2nd argument) which is more compact and suitable for
            # combo boxes and similar components. Note that if `col` is a registered
            # column, all metadata matches the registered one (otherwise we are not
            # here as the Form is invalid, see FlatfileForm and smtk/flatfile.py)
            columns.append(get_hr_flatfile_column_meta(col, dataframe[col]))

        return {'columns': columns}


class FlatfileMetadataInfoForm(GsimImtForm, APIForm):
    """Form for querying the necessary metadata columns from a given list of Gsims"""

    def clean_gsim(self) -> dict[str, Any]:
        """Custom gsim clean, allowing empty gsim parameter (=select all models)"""
        if not self.cleaned_data.get('gsim', None):
            return {n: None for n in models.Gsim.names()}  # dict values are not used
        return super().clean_gsim()

    def clean_imt(self) -> dict[str, Any]:
        """Custom imt clean, allowing empty imt parameter"""
        if not self.cleaned_data.get('imt', None):
            return {}
        return super().clean_imt()

    def clean(self):
        """skip the superclass `clean` method because we do not want to check
        imt and gsim compatibility
        """
        pass

    def output(self) -> dict:
        """Compute and return the output from the input data (`self.cleaned_data`).
        This method must be called after checking that `self.is_valid()` is True

        :return: any Python object (e.g., a JSON-serializable dict)
        """
        cleaned_data = self.cleaned_data
        gsims = list(cleaned_data['gsim'])

        ff_columns = {
            FlatfileMetadata.get_aliases(c)[0]
            for c in ground_motion_properties_required_by(*gsims)
        }

        imts = list(cleaned_data['imt'])

        columns = []
        for col in sorted(ff_columns | set(imts)):
            columns.append(get_hr_flatfile_column_meta(col))

        return {'columns': columns}


def get_hr_flatfile_column_meta(name: str, values: Optional[pd.Series] = None) -> dict:
    """Return human-readable (hr) flatfile column metadata in the following `dict` form:
    {
        'name': str,
        'help': str,
        'dtype': str,
        'type': str
    }

    :param name: the flatfile column name
    :param values: if provided, return meta info from the values. Otherwise, from the
        default flatfile column with the given name (if no column is registered with
        that name or alias, then return a dict with empty values)
    """
    if values is not None:
        try:
            c_categories = values.cat.categories
            c_dtype = get_dtype_of(c_categories)
        except AttributeError:
            c_categories = []
            c_dtype = get_dtype_of(values)
        c_type = ""
        c_help = ""
    else:
        c_dtype = FlatfileMetadata.get_dtype(name)
        c_categories = FlatfileMetadata.get_categories(name)
        c_type = getattr(FlatfileMetadata.get_type(name), 'value', "")
        c_help = FlatfileMetadata.get_help(name) or ""
        c_aliases = set(FlatfileMetadata.get_aliases(name)) - {name}
        if len(c_aliases):
            if c_help:
                c_help += '. '
            c_help += f'Alternative names: {", ".join(c_aliases)})'

    if c_dtype is not None:
        c_dtype = c_dtype.value
        if len(c_categories):
            if values is not None:  # custom values, compact categories info:
                c_dtype += f", categorical, {len(c_categories)} values"
            else:
                c_dtype += (f", categorical, to be chosen from "
                            f"{', '.join(str(c) for c in c_categories)}")
    else:
        c_dtype = ""

    return {
        'name': name,
        'type': c_type,
        'dtype': c_dtype,
        'help': c_help
    }


