"""
Base Form for to model-to-data operations i.e. flatfile handling
"""
from io import BytesIO
import re

import pandas as pd
from django.core.exceptions import ValidationError
from django.forms import Form
from django.utils.translation import gettext
from pandas.core.computation.ops import UndefinedVariableError
from smtk.residuals.gmpe_residuals import Residuals

from ... import models
from ...flatfile import read_flatfile, EgsimContextDB
from .. import EgsimBaseForm
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
                                help_text='The name of a preloaded flatfile (or '
                                          'Ground Motion Database)',
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
            u_flatfile = u_form.cleaned_data['flatfile']

        if u_flatfile is None:
            # exception should be raised and sent as 500: don't catch
            p_ff = cleaned_data["flatfile"]
            dataframe = pd.read_hdf(p_ff.filepath, key=p_ff.name)
        else:
            # u_ff = cleaned_data[key_u]
            try:
                dataframe = read_flatfilefrom_csv_bytes(BytesIO(u_flatfile))
            except Exception as exc:
                msg = str(exc)
                # Use 'flatfile' as error key: users can not be confused
                # (see __init__), and also 'flatfile' is also the exposed key
                # for the `files` argument in requests
                self.add_error("flatfile", ValidationError(gettext(msg),
                                                           code='invalid'))
                return cleaned_data  # noo need to further process

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


def read_flatfilefrom_csv_bytes(buffer, *, sep=None):
    dtype, defaults = models.FlatfileColumn.get_dtype_and_defaults()
    return read_flatfile(buffer, sep=sep, dtype=dtype,
                         defaults=defaults)


def reformat_selection_expression(dataframe, sel_expr):
    """Reformat the filter expression by changing `notna(column)` to
    column == column. Also change true/false to True/False
    """
    # `col == col` is the pandas query expression to filter rows that are not NA.
    # We implement a `notna(col)` expression which is more edible for the users.
    # Before replacing `notna`, first check that the argument is a column:
    notna_expr = r'\bnotna\((.*?)\)'
    for match in re.finditer(notna_expr, sel_expr):
        if match.group(1) not in dataframe.olumns:
            # raise the same pandas excpetion:
            raise UndefinedVariableError(match.group(1))
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
    context_db = EgsimContextDB(flatfile, *flatfile_colnames())
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


def flatfile_colnames() -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    """Return rupture, site distance parameters as three dicts of
    flatfile column names mapped to the relative Context attribute used
    for residuals computation
    """
    qry = models.FlatfileColumn.objects  # noqa
    qry = qry.filter(name__isnull=False, oq_name__isnull=False)
    rup, site, dist = {}, {}, {}
    for ffname, attname, categ in qry.values_list('name', 'oq_name', 'category'):
        if categ == models.FlatfileColumn.CATEGORY.RUPTURE_PARAMETER:
            rup[ffname] = attname
        elif categ == models.FlatfileColumn.CATEGORY.SITE_PARAMETER:
            site[ffname] = attname
        elif categ == models.FlatfileColumn.CATEGORY.DISTANCE_MEASURE:
            dist[ffname] = attname
    return rup, site, dist
