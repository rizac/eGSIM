"""
Base Form for to model-to-data operations i.e. flatfile handling
"""
from collections import defaultdict

import re
from datetime import datetime
from typing import Iterable, Sequence, Any

import pandas as pd
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import Form, ModelChoiceField
from pandas.errors import UndefinedVariableError
from smtk.residuals.gmpe_residuals import Residuals

from ... import models
from ....smtk.flatfile import (read_flatfile, EgsimContextDB, ColumnMetadata)
from .. import EgsimBaseForm, GsimImtForm, APIForm, _get_gsim_choices
from ..fields import CharField, FileField, MultipleChoiceWildcardField


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

    flatfile = ModelChoiceField(queryset=models.Flatfile.get_flatfiles(),
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
                selexpr = reformat_selection_expression(dataframe, selexpr)
                cleaned_data['flatfile'] = dataframe.query(selexpr).copy()
            except Exception as exc:
                # add_error removes also the field from self.cleaned_data:
                self.add_error(key, ValidationError(str(exc), code='invalid'))

        return cleaned_data

    @classmethod
    def read_flatfile_from_db(cls, model_instance: models.Flatfile) -> pd.DataFrame:
        return pd.read_hdf(model_instance.filepath, key=model_instance.name)  # noqa

    @classmethod
    def read_flatfilefrom_csv_bytes(cls, buffer, *, sep=None) -> pd.DataFrame:
        dtype, defaults, _, required = models.FlatfileColumn.get_data_properties()
        # pre rename of IMTs lower case (SA excluded):
        # (skip, just use the default of read_flatfile: PGA, PGV, SA):
        # imts = models.Imt.objects.only('name').values_list('name', flat=True)
        return read_flatfile(buffer, sep=sep, dtype=dtype, defaults=defaults,
                             required=required)

    @classmethod
    def get_flatfile_dtypes(cls, flatfile: pd.DataFrame,
                                compact=False) -> dict[str, str]:
        """Return the data types description of the given flatfile in eGSIM format:
        'str', 'int', 'float', 'bool', 'datetime', list (for categorical data).

        :param compact: if True, categorical data will be returned as human
            readable string instead of the list of categories, which might be
            huge in size
        """
        dtypes = {}
        ff_dtypes = ColumnMetadata.BaseDtype  # Enum
        for col in flatfile.columns:
            pd_dtype = str(flatfile[col].dtype)
            categories = None
            if pd_dtype == 'category':
                categories = flatfile[col].dtype.categories
                pd_dtype = str(categories.dtype)

            dtype = None
            if pd_dtype == 'object':
                dtype = ff_dtypes.str.name
            elif pd_dtype.startswith('int'):
                dtype = ff_dtypes.int.name
            elif pd_dtype.startswith('float'):
                dtype = ff_dtypes.float.name
            elif pd_dtype.startswith('datetime'):
                dtype = ff_dtypes.datetime.name
            else:
                try:
                    dtype = ff_dtypes[pd_dtype].name
                except KeyError:
                    pass

            if dtype is None:
                suffix = '' if categories is None else ' (categorical)'
                raise ValueError(f'Unsupported data type for column '
                                 f'"{col}": {pd_dtype}{suffix}')

            if categories is not None:
                if compact:
                    dtype = f'{dtype} (selectable from ' \
                            f'{len(categories)} discrete values)'
                else:
                    dtype = flatfile[col].dtype.categories.tolist()

            dtypes[col] = dtype
        return dtypes


#############
# Utilities #
#############


class MOF:  # noqa
    # simple class emulating an Enum
    RES = 'res'
    LH = 'l'
    LLH = "ll"
    MLLH = "mll"
    EDR = "edr"


def reformat_selection_expression(dataframe, sel_expr) -> str:
    """Reformat the filter expression by changing `notna(column)` to
    column == column. Also change true/false to True/False
    """
    # `col == col` is the pandas query expression to filter rows that are not NA.
    # We implement a `notna(col)` expression which is more edible for the users.
    # Before replacing `notna`, first check that the argument is a column:
    notna_expr = r'\bnotna\((.*?)\)'
    for match in re.finditer(notna_expr, sel_expr):
        # check that the column inside the expression is valid:
        cname = match.group(1)
        # if col contains invalid chars, thus i wrapped in ``:
        if len(cname) > 1 and cname[0] == cname[-1] == '`':
            cname = cname[1:-1]
        if cname not in dataframe.columns:
            # raise the same pandas exception:
            raise UndefinedVariableError(cname)
    # now replace `notna(x)` with `x == x` (`isna` can be typed as `~notna`):
    sel_expr = re.sub(notna_expr, r"(\1==\1)", sel_expr, re.IGNORECASE)
    # be relaxed about booleans: accept any case (lower, upper, mixed):
    sel_expr = re.sub(r'\btrue\b', "True", sel_expr, re.IGNORECASE)
    sel_expr = re.sub(r'\bfalse\b', "False", sel_expr, re.IGNORECASE)
    return sel_expr


def get_residuals(flatfile: pd.DataFrame, gsim: list[str], imt: list[str]) -> Residuals:
    """Instantiate a Residuals object with computed residuals. Wrap missing
    flatfile columns into a ValidationError so that it can be returned as
    "client error" (4xx) response
    """
    context_db = EgsimContextDB(flatfile, *ctx_flatfile_colnames())
    residuals = Residuals(gsim, imt)
    try:
        residuals.get_residuals(context_db)
        return residuals
    except KeyError as kerr:
        # A key error usually involves a missing column. If yes, raise
        # ValidationError
        col = str(kerr.args[0]) if kerr.args else ''
        if col in context_db.flatfile_columns:
            raise ValidationError('Missing column "%(col)s" in flatfile',
                                  code='invalid',
                                  params={'col': col})
        # raise "normally", as any other exception not caught here
        raise kerr


def ctx_flatfile_colnames() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Return rupture, site distance parameters as three `dict`s of
    flatfile column names mapped to the relative Context attribute used
    for residuals computation
    """
    qry = models.FlatfileColumn.objects  # noqa
    rup, site, dist = {}, {}, {}
    cols = 'name', 'oq_name', 'category'
    for ffname, attname, categ in qry.only(*cols).values_list(*cols):
        if categ == ColumnMetadata.Category.rupture_parameter:
            rup[ffname] = attname
        elif categ == ColumnMetadata.Category.site_parameter:
            site[ffname] = attname
        elif categ == ColumnMetadata.Category.distance_measure:
            dist[ffname] = attname
    return rup, site, dist


# Form handling Gsims and flatfile:

class GsimImtFlatfileForm(GsimImtForm, FlatfileForm):

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


def get_gsims_from_flatfile(flatfile_columns: Sequence[str]) -> Iterable[str]:
    """Yields the GSIM names supported by the given flatfile"""
    ff_cols = set('SA' if _.startswith('SA(') else _ for _ in flatfile_columns)
    model2cols = defaultdict(set)
    # filter models by imts (feasible via SQL) and build a dict of models with the
    # relatvie required flatfile columns (filter donw below, not possible to do in SQL):
    for model_name, required_fcol in models.Gsim.objects.filter(imts__name__in=ff_cols).\
            values_list('name', 'required_flatfile_columns__name'):
        model2cols[model_name].add(required_fcol)
    # filter on required flatfile columns and yields supported models:
    for model_name, cols in model2cols.items():
        if not cols - ff_cols:
            yield model_name

class FlatfileRequiredColumnsForm(APIForm):
    """Form for querying the necessary metadata columns from a given list of Gsims"""

    # Custom API param names (see doc of `EgsimBaseForm._field2params` for details):
    _field2params = {'gsim' : GsimImtForm._field2params['gsim']}  # noqa

    gsim = MultipleChoiceWildcardField(required=False, choices=_get_gsim_choices,
                                       label='Ground Shaking Intensity Model(s)')


    @classmethod
    def process_data(cls, cleaned_data: dict) -> dict:
        """Process the input data `cleaned_data` returning the response data
        of this form upon user request.
        This method is called by `self.response_data` only if the form is valid.

        :param cleaned_data: the result of `self.cleaned_data`
        """
        qry = models.FlatfileColumn.objects  # noqa

        required = set()
        if cleaned_data.get('gsim', []):
            required = set(qry.only('name').
                           filter(Q(gsims__name__in=cleaned_data['gsim']) |
                                  Q(required=True)).
                           values_list('name', flat=True))

        columns = {}
        attrs = 'name', 'help', 'data_properties'
        for name, help, props in qry.only(*attrs).values_list(*attrs):
            columns[name] = {}
            if not required or name in required:
                columns[name] = {'help': help, 'dtype': props['dtype']}

        return columns

    @classmethod
    def csv_rows(cls, processed_data: dict) -> Iterable[Iterable[Any]]:
        """Yield CSV rows, where each row is an iterables of Python objects
        representing a cell value. Each row doesn't need to contain the same
        number of elements, the caller function `self.to_csv_buffer` will pad
        columns with Nones, in case (note that None is rendered as "", any other
        value using its string representation).

        :param processed_data: dict resulting from `self.process_data`
        """
        names = processed_data.keys()
        yield names
        yield (processed_data[n].get('help', '') for n in names)
        yield (processed_data[n].get('dtype', '') for n in names)
