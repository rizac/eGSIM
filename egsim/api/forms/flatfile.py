"""
Base Form for to model-to-data operations i.e. flatfile handling
"""
from io import BytesIO
from typing import Optional
import pandas as pd
from django.core.files.uploadedfile import TemporaryUploadedFile

from django.forms import Form
from django.forms.fields import CharField, FileField

from egsim.smtk import (ground_motion_properties_required_by, FlatfileError,
                        intensity_measures_defined_for, get_sa_limits)
from egsim.smtk.flatfile import (read_flatfile, get_dtype_of, FlatfileMetadata,
                                 query as flatfile_query, EVENT_ID_COLUMN_NAME)
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
                self.add_error("flatfile", f"only one flatfile should be uploaded "
                                           f"(found {len(ff_keys)})")
                return cleaned_data
            # Accessing the only key of u_form.files us a list of - or in this case,
            # our only UploadedFile
            # (https://docs.djangoproject.com/en/5.0/ref/files/uploads/):
            u_flatfile = u_form.files[ff_keys[0]]
            # If the uploaded file is too big, Django writes it to a Temporary file, and
            # we need a workaround (read from disk) to get the whole file content:
            if isinstance(u_flatfile, TemporaryUploadedFile):
                with open(u_flatfile.temporary_file_path(), 'rb') as _:
                    u_flatfile = BytesIO(_.read())
            else:
                u_flatfile = u_flatfile.file  # BytesIO object or alike

        if u_flatfile is None:  # predefined flatfile
            flatfile_db_obj = models.Flatfile.queryset('name', 'media_root_path').\
                filter(name=cleaned_data['flatfile']).first()
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
            except Exception as exc:
                # add_error removes also the field from self.cleaned_data:
                self.add_error(key, str(exc))

        return cleaned_data


class FlatfileValidationForm(APIForm, FlatfileForm):
    """Form for flatfile validation, on success
    return info from a given uploaded flatfile"""

    def output(self) -> Optional[dict]:
        """
        Compute and return the output from the input data (`self.cleaned_data`).
        This method must be called after checking that `self.is_valid()` is True.

        :return: any Python object (e.g., a JSON-serializable dict)
        """
        cleaned_data = self.cleaned_data
        dataframe = cleaned_data['flatfile']
        columns = []
        for col in sorted(dataframe.columns):
            # return human-readable column metadata from its values (dataframe[col]).
            # Note that if `col` is a registered column, then all metadata match the
            # registered one (otherwise we should never be here because
            # `self.is_valid` is False. See FlatfileForm and smtk/flatfile.py)
            columns.append(get_hr_flatfile_column_meta(col, dataframe[col]))

        return {'columns': columns}


class FlatfileMetadataInfoForm(GsimImtForm, APIForm):
    """Form for querying the necessary metadata columns from a given selection
    of models"""

    def clean_imt(self) -> set[str]:
        """
        intensity measures should be given as type / class name (e.g. SA not "SA(P)").
        If empty, this parameter will default to all available IMTs
        """
        value = self.cleaned_data.get('imt', None)
        aval_imts = FlatfileMetadata.get_intensity_measures()
        if not value:
            return aval_imts
        if type(value) not in (list, tuple):
            value = [value]
        value = set(value)
        if value - aval_imts:
            self.add_error('imt', self.ErrMsg.invalid)
        return value

    def clean(self):
        """skip the superclass `clean` method because we do not want to check
        imt and gsim compatibility
        """
        unique_imts = self.cleaned_data['imt']

        for m_name, model in self.cleaned_data['gsim'].items():
            imts = intensity_measures_defined_for(model)
            unique_imts &= set(imts)
            if not unique_imts:
                break

        if 'SA' in unique_imts:
            min_p, max_p = [], []
            for m_name, model in self.cleaned_data['gsim'].items():
                p_bounds = get_sa_limits(model)
                if p_bounds is None:
                    # FIXME: we assume a model supporting SA with no period limits
                    #  is defined for all periods, but is it true?
                    continue
                min_p.append(p_bounds[0])
                max_p.append(p_bounds[1])
            min_p = max(min_p)
            max_p = min(max_p)
            if max_p < min_p:
                unique_imts -= {'SA'}
            else:
                self.cleaned_data['sa_period_limits'] = [min_p, max_p]

        if not unique_imts:
            self.add_error('gsim', 'No intensity measure defined for all models')
        return self.cleaned_data

    def output(self) -> dict:
        """Compute and return the output from the input data (`self.cleaned_data`).
        This method must be called after checking that `self.is_valid()` is True

        :return: any Python object (e.g., a JSON-serializable dict)
        """
        cleaned_data = self.cleaned_data
        gsims = list(cleaned_data['gsim'])

        required_columns = (ground_motion_properties_required_by(*gsims) |
                            {EVENT_ID_COLUMN_NAME})  # <- event id always required
        ff_columns = {FlatfileMetadata.get_aliases(c)[0] for c in required_columns}

        imts = cleaned_data['imt']

        columns = []
        sa_period_limits = cleaned_data.get('sa_period_limits', None)
        for col in sorted(ff_columns | set(imts)):
            columns.append(get_hr_flatfile_column_meta(col))
            if col == 'SA':
                sa_p_min, sa_p_max = sa_period_limits
                help_ = columns[-1]['help'].split('.')
                new_text = (f' <b>The period range supported by all selected model(s) '
                            f'is [{sa_p_min}, {sa_p_max}] (endpoints included)</b>'
                            if sa_p_min < sa_p_max else
                            f' <b>The only period supported by all selected model(s) '
                            f'is {sa_p_min}</b>')
                help_.insert(2, new_text)
                if sa_p_min == sa_p_max:
                    # only one period: remove last part were we talk about interpolating
                    help_ = help_[:3]
                columns[-1]['help'] = ".".join(help_)

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
    :param values: if provided, return metadata from the values. Otherwise, return
        metadata registered for the flatfile column with the given name (if no column
        is registered with that name or alias, then return a dict with empty values)
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
        c_aliases = FlatfileMetadata.get_aliases(name)
        if len(c_aliases) > 1:
            c_aliases = [n for n in c_aliases if n != name]
            c_aliases = (f"Alternative valid name{'s' if len(c_aliases) != 1 else ''}: "
                         f"{', '.join(c_aliases)}")
            if c_help:
                c_help += f". {c_aliases}"
            else:
                c_help = c_aliases

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
