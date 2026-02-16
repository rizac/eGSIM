"""Base Form for to model-to-data operations i.e. flatfile handling"""

import pandas as pd
from django.core.files.uploadedfile import TemporaryUploadedFile

from django.forms import Form
from django.forms.fields import CharField, FileField

from egsim.smtk.registry import (
    ground_motion_properties_required_by,
    intensity_measures_defined_for,
    sa_limits
)
from egsim.smtk.flatfile import (
    read_flatfile,
    get_dtype_of,
    column_exists,
    column_type,
    column_aliases,
    column_dtype,
    column_help,
    query as flatfile_query,
    EVENT_ID_COLUMN_NAME,
    FlatfileError,
    FlatfileQueryError,
    IncompatibleColumnError,
    column_names
)
from egsim.api import models
from egsim.api.forms import EgsimBaseForm, APIForm, GsimForm, split_periods


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
        'selexpr': ('flatfile-query', 'data-query'),
        'flatfile': ('flatfile', 'data')
    }
    flatfile = CharField(
        required=False,
        help_text="The flatfile (pre- or user-defined) containing observed ground "
                  "motion properties and intensity measures, in CSV or HDF format"
    )  # Note: CharField + custom validation in `clean` is better than ModelChoiceField
    selexpr = CharField(
        required=False,
        help_text='Filter flatfile records (rows) matching query expressions applied '
                  'on the columns, e.g.: "(mag > 6) & (rrup < 10)" (&=and, |=or)'
    )

    def __init__(self, data, files=None, **kwargs):
        self._uploaded_flatfile_form = None
        if files is not None:
            self._uploaded_flatfile_form = _UploadedFlatfile(files=files)
        super().__init__(data=data, **kwargs)

    def clean(self):
        """Call `super.clean()` and handle the flatfile"""

        u_form = self._uploaded_flatfile_form

        # Handle flatfiles conflicts first. Note: with no selection from the web GUI we
        # have data['flatfile'] = None
        if u_form is not None and self.data.get('flatfile', None):
            self.add_error(
                "flatfile",
                'select a flatfile by name or upload one, not both'
            )
        elif u_form is None and not self.data.get('flatfile', None):
            # note: with no selection from the web GUI we have data['flatfile'] = None
            self.add_error("flatfile",  self.ErrMsg.required)

        cleaned_data = super().clean()

        if self.has_error('flatfile'):
            return cleaned_data

        u_flatfile = None  # None or bytes object

        if u_form is not None:
            if not u_form.is_valid():
                self._errors = u_form._errors
                return cleaned_data
            # u_form.files is a MultiValueDict or a dict (I guss the latter when
            # we do provide a flatfile). We do not care about the keys as long as
            # there is just one key:
            ff_keys = list(u_form.files.keys())
            if len(ff_keys) != 1:
                self.add_error(
                    "flatfile",
                    f"only one flatfile should be uploaded (found {len(ff_keys)})"
                )
                return cleaned_data
            # Get our uploaded file (Django UploadedFile object, for ref see
            # https://docs.djangoproject.com/en/5.0/ref/files/uploads/):
            uploaded_flatfile = u_form.files[ff_keys[0]]
            if isinstance(uploaded_flatfile, TemporaryUploadedFile):
                # File on disk (Django TemporaryUploadedFile object), get the path:
                u_flatfile = uploaded_flatfile.temporary_file_path()
            else:
                # in-memory file (Django UploadedFile object), get the Python
                # file-like object:
                u_flatfile = uploaded_flatfile.file
            # Note: as of pandas 2.2.2, HDF does not support reading from stream
            # or buffer. As such, we force every uploaded flatfile to be a
            # TemporaryUploadedFile (via settings.FILE_UPLOAD_MAX_MEMORY_SIZE = 0),
            # and in-memory files are used only in some tests

        if u_flatfile is None:  # predefined flatfile
            flatfile_db_obj = models.Flatfile.queryset(
                'name',
                'filepath'
            ).filter(name=cleaned_data['flatfile']).first()
            if flatfile_db_obj is None:
                self.add_error("flatfile", self.ErrMsg.invalid_choice)
                return cleaned_data
            # cleaned_data["flatfile"] is a models.Flatfile instance:
            dataframe = flatfile_db_obj.read_from_filepath()
        else:  # uploaded (user-defined) flatfile
            try:
                # u_flatfile is a Django TemporaryUploadedFile or InMemoryUploadedFile
                # (the former if file size > configurable threshold
                # (https://stackoverflow.com/a/10758350):
                dataframe = read_flatfile(u_flatfile)
            except IncompatibleColumnError as ice:
                self.add_error(
                    'flatfile', f'column names conflict {str(ice)}'
                )
                return cleaned_data
            except FlatfileError as err:
                self.add_error("flatfile", str(err))
                return cleaned_data  # no need to further process

        # replace the flatfile parameter with the pandas dataframe:
        cleaned_data['flatfile'] = dataframe

        key = 'selexpr'
        selexpr = cleaned_data.get(key, None)
        if selexpr:
            try:
                cleaned_data['flatfile'] = flatfile_query(dataframe, selexpr).copy()
            except FlatfileQueryError as exc:
                # add_error removes also the field from self.cleaned_data:
                self.add_error(key, str(exc))

        return cleaned_data


class FlatfileValidationForm(APIForm, FlatfileForm):
    """
    Form for flatfile validation, on success return info from the uploaded flatfile
    """
    def output(self) -> dict:
        """
        Compute and return the output from the input data (`self.cleaned_data`),
        which is a dict with all flatfile columns info.
        This method must be called after checking that `self.is_valid()` is True.

        :return: any Python object (e.g., a JSON-serializable dict)
        """
        # return human-readable column metadata from its values (dataframe[col]).
        cleaned_data = self.cleaned_data
        dataframe = cleaned_data['flatfile']
        columns = [
            get_hr_flatfile_column_meta(col, dataframe[col])
            for col in sorted(dataframe.columns)
        ]

        return {'columns': columns}


class FlatfileMetadataInfoForm(GsimForm, APIForm):
    """
    Form for querying the necessary metadata columns from a given selection of models
    """
    def clean(self):
        cleaned_data = super().clean()
        unique_imts = column_names(type='intensity')

        for m_name, model in cleaned_data['gsim'].items():
            imts = intensity_measures_defined_for(model)
            unique_imts &= set(imts)
            if not unique_imts:
                break

        if 'SA' in unique_imts:
            min_p, max_p = get_sa_limits(cleaned_data['gsim'].values())
            if min_p > max_p:
                unique_imts -= {'SA'}

        if not unique_imts:
            self.add_error(
                'gsim', 'No intensity measure defined for all models'
            )

        cleaned_data['imt'] = sorted(unique_imts)
        return cleaned_data

    def output(self) -> dict:
        """
        Compute and return the output from the input data (`self.cleaned_data`).
        This method must be called after checking that `self.is_valid()` is True

        :return: any Python object (e.g., a JSON-serializable dict)
        """
        cleaned_data = self.cleaned_data
        gsims = list(cleaned_data['gsim'].values())
        required_columns = (  # event id always required
            ground_motion_properties_required_by(*gsims) | {EVENT_ID_COLUMN_NAME}
        )
        ff_columns = {column_aliases(c)[0] for c in required_columns}
        imts = cleaned_data['imt']

        columns = []
        for col in sorted(ff_columns | set(imts)):
            col_info = get_hr_flatfile_column_meta(col)
            if col == 'SA':
                col_info['help'] = get_sa_help(gsims)
            columns.append(col_info)

        return {'columns': columns}


def get_hr_flatfile_column_meta(name: str, values: pd.Series | None = None) -> dict:
    """
    Return human-readable (hr) flatfile column metadata in the following `dict` form:
    {
        'name': str,
        'help': str,
        'dtype': str,
        'type': str
    }

    :param name: the flatfile column name
    :param values: the column data, ignored if `name` is a registered flatfile column.
        Otherwise, if provided, it will be used to infer the column metadata
    """
    c_type = ""
    c_help = ""
    c_dtype = None
    c_categories = []

    if column_exists(name):
        c_dtype = column_dtype(name)
        if isinstance(c_dtype, pd.CategoricalDtype):
            c_categories = c_dtype.categories.tolist()
            c_dtype = get_dtype_of(c_dtype.categories)
        c_type = getattr(column_type(name), 'value', "")
        c_help = column_help(name) or ""
        c_aliases = column_aliases(name)
        if len(c_aliases) > 1:
            c_aliases = [n for n in c_aliases if n != name]
            c_aliases = (
                f"Alternative valid name{'s' if len(c_aliases) != 1 else ''}: "
                f"{', '.join(c_aliases)}"
            )
            if c_help:
                c_help += f". {c_aliases}"
            else:
                c_help = c_aliases
    elif values is not None:
        try:
            c_categories = values.cat.categories
            c_dtype = get_dtype_of(c_categories)
        except AttributeError:
            c_categories = []
            c_dtype = get_dtype_of(values)

    if c_dtype is not None:
        c_dtype = c_dtype.value
        if len(c_categories):
            if values is not None:  # custom values, compact categories info:
                c_dtype += f", categorical, {len(c_categories)} values"
            else:
                c_dtype += (
                    f", categorical, to be chosen from "
                    f"{', '.join(str(c) for c in c_categories)}"
                )
    else:
        c_dtype = ""

    return {
        'name': name,
        'type': c_type,
        'dtype': c_dtype,
        'help': c_help
    }


def get_sa_limits(gsims) -> tuple[float, float]:
    """Return the SA period limits that work with all the given ground motion models.
    Return [-float('inf'), float('inf')] if no period bound can be found, i.e.,
    when no models have SA period limits defined (which might be due to no model
    being defined for SA, this is not checked for here).
    If the first element is greater than the second element, it means
    that there is no overlapping SA period for the given models.

    :param gsims: iterable of ground motion models (str or GMPE instances)
    """
    inf = float('inf')
    min_p, max_p = -inf, inf
    # for m_name, model in cleaned_data['gsim'].items():
    for gsim in gsims:
        p_bounds = sa_limits(gsim)
        if p_bounds is None:
            # FIXME: we assume a model supporting SA with no period limits
            #  is defined for all periods, but is it true?
            continue
        min_p = max(min_p, p_bounds[0])
        max_p = min(max_p, p_bounds[1])
    return min_p, max_p


def get_sa_help(gsims) -> str:
    """
    Build the SA field help, human-readable (hr) from the flatfile SA help,
    adding the info about the allowed SA periods common to all the given
    ground motion models `gsims`
    """
    sa_help = column_help('SA')
    sa_p_min, sa_p_max = get_sa_limits(gsims)
    if not (-float('inf') < sa_p_min <= sa_p_max < float('inf')):
        return sa_help

    if len(gsims) > 1:
        the_selected_model = f'all {len(gsims)} selected models'
    else:
        the_selected_model = 'the selected model'

    if sa_p_min < sa_p_max:
        new_text = (
            f'The period range supported by {the_selected_model} '
            f'is [{sa_p_min}, {sa_p_max}] (endpoints included)'
        )
    else:
         new_text = (
             f'The only period supported by {the_selected_model} is {sa_p_min}'
         )

    help_pars = split_periods(sa_help)
    help_pars = help_pars[:2] + [f'<b>{new_text}</b>. '] + help_pars[2:]
    return " ".join(s.strip() for s in help_pars)
