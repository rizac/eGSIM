"""
Base Form for to model-to-data operations i.e. flatfile handling
"""
import re
from datetime import datetime
from typing import Iterable, Sequence, Any

import pandas as pd
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.forms import Form
from django.utils.translation import gettext
from pandas.core.computation.ops import UndefinedVariableError
from smtk.residuals.gmpe_residuals import Residuals

from ... import models
from ...flatfile import read_flatfile, EgsimContextDB, REQUIRED_COLUMNS, get_imt
from .. import EgsimBaseForm, GsimImtForm
from ..fields import ModelChoiceField, CharField, FileField


# Let's provide uploaded flatfile Field in a separate Form as the Field is not
# strictly JSON-encodable (info here: https://stackoverflow.com/a/4083908) and
# should be kept private/hidden by default:
class _UploadedFlatfile(Form):
    flatfile = FileField(required=False)  # keep same name as flatfile below


class FlatfileForm(EgsimBaseForm):
    """Base Form for handling Flatfiles"""

    # Set the public names of this Form Fields as `public_name: attribute_name`
    # mappings. Superclass mappings are merged into this one. An attribute name
    # can be keyed by several names, and will be keyed by itself anyway if not
    # done here (see `egsim.forms.EgsimFormMeta` for details)
    public_field_names = {
        'flatfile': 'flatfile', 'gmdb': 'flatfile',
        'selexpr': 'selexpr', 'sel': 'selexpr',
    }

    flatfile = ModelChoiceField(queryset=models.Flatfile.get_flatfiles(),
                                to_field_name="name", label='Flatfile',
                                empty_label=None, required=False)
    selexpr = CharField(required=False, label='Selection expression')

    def __init__(self, data, files=None, **kwargs):
        super().__init__(data=data, **kwargs)  # <- normalizes data keys
        self._u_ff = None if files is None else _UploadedFlatfile(files=files)

    def clean(self):
        """Call `super.clean()` and handle the flatfile"""
        u_form = self._u_ff

        flatfile_conflicts = False
        # Handle flatfiles conflicts first. Note: with no selection from the web GUI we
        # have data['flatfile'] = None
        if u_form is not None and self.data.get('flatfile', None):
            flatfile_conflicts = True
            self.add_error("flatfile", ValidationError('Please either select a '
                                                       'flatfile, or upload one',
                                                       code='conflict'))
        elif u_form is None and not self.data.get('flatfile', None):
            flatfile_conflicts = True
            # note: with no selection from the web GUI we have data['flatfile'] = None
            self.add_error("flatfile",  ValidationError('Please select a flatfile '
                                                        'or upload one',
                                                        code='required'))

        cleaned_data = super().clean()

        if flatfile_conflicts:
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
            dataframe = pd.read_hdf(p_ff.filepath, key=p_ff.name)
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
                self.add_error("flatfile", ValidationError(gettext(msg),
                                                           code='invalid'))
                return cleaned_data  # no need to further process

            # check data types:
            invalid_cols = self.get_flatfile_columns_with_invalid_dtypes(dataframe)
            if invalid_cols:
                # FIXME: gettext?
                err_gsim = ValidationError(gettext("%(num)d columns(s) have invalid "
                                                   "data types (e.g., str whereas "
                                                   "int is expected)"),
                                           params={'num': len(invalid_cols)},
                                           code='invalid')
                # add_error removes also the field from self.cleaned_data:
                self.add_error('flatfile', err_gsim)
                return cleaned_data

        key = 'selexpr'
        selexpr = cleaned_data.get(key, None)
        if selexpr:
            try:
                selexpr = reformat_selection_expression(dataframe, selexpr)
                dataframe = dataframe.query(selexpr).copy()
            except Exception as exc:
                # add_error removes also the field from self.cleaned_data:
                self.add_error(key, ValidationError(str(exc), code='invalid'))
                return cleaned_data  # no need to further processing

        # replace the flatfile parameter with the pandas dataframe:
        cleaned_data['flatfile'] = dataframe
        return cleaned_data

    @classmethod
    def read_flatfilefrom_csv_bytes(cls, buffer, *, sep=None) -> pd.DataFrame:
        dtype, defaults = models.FlatfileColumn.get_dtype_and_defaults()
        # pre rename of IMTs lower case (SA excluded):
        # (skip, just use the default of read_flatfile: PGA, PGV, SA):
        # imts = models.Imt.objects.only('name').values_list('name', flat=True)
        return read_flatfile(buffer, sep=sep, dtype=dtype, defaults=defaults)

    @classmethod
    def get_flatfile_columns_with_invalid_dtypes(cls, flatfile: pd.DataFrame) -> \
            Sequence[tuple[str, Any, Any]]:
        """return tuple (col, dtype, expected_dtype) elements"""
        standard_dtypes, _ = models.FlatfileColumn.get_dtype_and_defaults()
        ff_dtypes = cls.get_flatfile_dtypes(flatfile)
        bad_cols = []
        for col in set(standard_dtypes) & set(ff_dtypes):
            expected_dtype = standard_dtypes[col]
            ff_dtype = ff_dtypes[col]
            if expected_dtype == ff_dtype:
                continue
            if expected_dtype == 'int' and ff_dtype == 'float':
                continue
            if isinstance(expected_dtype, list) and isinstance(ff_dtype, list) \
                    and sorted(expected_dtype) == sorted(ff_dtype):
                continue
            bad_cols.append((col, ff_dtype, expected_dtype))

        return bad_cols

    @classmethod
    def get_flatfile_dtypes(cls, flatfile: pd.DataFrame) -> dict[str, str]:
        """Return the data types of the given flatfile in eGSIM format:
        'str', 'int', 'float', 'bool', 'datetime', list (for categorical data).

        The data types above must be consistent with those implemented in:
        `api.management.gsim_params.py` which writes data types from the YAML into
        `models.FlatfileColumn` (`property` column)
        """
        dtypes = {}
        for c in flatfile.columns:
            dtype = str(flatfile[c].dtype)
            if dtype.startswith('int'):
                dtype = 'int'
            elif dtype.startswith('float'):
                dtype = 'float'
            elif dtype.startswith('datetime'):
                dtype = 'datetime'
            elif dtype == 'object':
                dtype = 'str'
            elif dtype == 'category':
                dtype = flatfile[c].dtype.categories.tolist()
            elif dtype != 'bool':
                raise ValueError(f'Unsupported data type for column "{c}": "{dtype}"')
            dtypes[c] = dtype
        return dtypes

#############
# Utilities #
#############


class MOF:  # noqa
    # simple class emulating an Enum
    RES = 'res'
    LH = 'lh'
    LLH = "llh"
    MLLH = "mllh"
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
        if categ == models.FlatfileColumn.Category.RUPTURE_PARAMETER:
            rup[ffname] = attname
        elif categ == models.FlatfileColumn.Category.SITE_PARAMETER:
            site[ffname] = attname
        elif categ == models.FlatfileColumn.Category.DISTANCE_MEASURE:
            dist[ffname] = attname
    return rup, site, dist


# Form handling Gsims and flatfile:

class GsimImtFlatfileForm(GsimImtForm, FlatfileForm):

    def clean(self):
        cleaned_data = super().clean()
        if 'flatfile' in cleaned_data:
            flatfile = cleaned_data['flatfile']
            if 'gsim' in cleaned_data:
                invalid_gsims = \
                    self.get_flatfile_invalid_gsim(flatfile, cleaned_data['gsim'])
                if invalid_gsims:
                    # FIXME: gettext?
                    err_gsim = ValidationError(gettext("%(num)d gsim(s) not supported "
                                                       "by the given flatfile"),
                                               params={'num': len(invalid_gsims)},
                                               code='invalid')
                    # add_error removes also the field from self.cleaned_data:
                    self.add_error('gsim', err_gsim)
                    cleaned_data.pop('flatfile')
                    return cleaned_data

        return cleaned_data

    @classmethod
    def get_flatfile_invalid_gsim(cls, flatfile: pd.DataFrame,
                                  gsims: Sequence[str]) -> set[str, ...]:
        return set(gsims) - set(flatfile_supported_gsims(flatfile.columns))


def flatfile_supported_gsims(flatfile_columns: Sequence[str]) -> Iterable[str]:
    """Yields the GSIM names supported by the given flatfile"""
    ff_imts = set()
    ff_metadata = set()
    for col in flatfile_columns:
        imt = get_imt(col, ignore_case=False)
        if imt is not None:
            ff_imts.add('SA' if imt.startswith('SA(') else imt)
        elif col not in REQUIRED_COLUMNS:
            ff_metadata.add(col)

    for gsim, gsim_metadata, gsim_imts in _get_gsim_columns_imts():
        if gsim_metadata.issubset(ff_metadata) and (gsim_imts & ff_imts):
            yield gsim


def _get_gsim_columns_imts() -> Iterable[tuple[str, set[str, ...], set[str, ...]]]:
    """Yields tuples of model names and associated flatfile columns and imts.
    Each yielded tuple is:
    ```
    (gsim:str, flatfile_columns:set[str], imts:set[str])
    ```
    """

    qry = models.Gsim.objects.only('name').prefetch_related(
        Prefetch('required_flatfile_columns',
                 queryset=models.FlatfileColumn.objects.all().only('name')),
        Prefetch('imts', queryset=models.Imt.objects.all().only('name')))

    for gsim in qry:
        ff_cols = set(_.name for _ in gsim.required_flatfile_columns.all())
        imts = set(_.name for _ in gsim.imts.all())
        yield gsim.name, ff_cols, imts
