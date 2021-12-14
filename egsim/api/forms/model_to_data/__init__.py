"""Common utilities for forms related to model-to-data operations, i.e.
involving flatfiles
"""
from io import BytesIO
import re

import pandas as pd
from django.core.exceptions import ValidationError
from django.utils.translation import gettext
from pandas.core.computation.ops import UndefinedVariableError
from smtk.residuals.gmpe_residuals import Residuals

from ... import models
from ...flatfile import read_flatfile, EgsimContextDB
from ..fields import ModelChoiceField, CharField, FileField
from ..forms import EgsimBaseForm


class FlatfileForm(EgsimBaseForm):
    """Abstract-like class for handling Flatfiles (either pre- or user-defined)"""

    # For each Field of this Form: the attribute name MUST NOT CHANGE, because
    # code relies on it (see e.g. keys of `cleaned_data`). The attribute value
    # can change as long as it inherits from `egsim.forms.fields.ParameterField`

    flatfile = ModelChoiceField('flatfile',
                                queryset=models.Flatfile.get_flatfiles(),
                                empty_label=None, label='Flatfile',
                                to_field_name="name", required=False)
    selexpr = CharField('selexpr',
                        required=False, label='Selection expression')
    # this is the Django field should NOT be a REST API parameter, as the files
    # are provided via a separate argument (https://stackoverflow.com/a/22567429)
    # As such, its parameter name (flatfile) can be shared with the flatifle
    # field attribute above
    uploaded_flatfile = FileField('flatfile',
                                  required=False, label='Flatfile upload')

    def clean(self):
        """Call `super.clean()` and handle the flatfile"""

        cleaned_data = super().clean()
        # check flatfiles. Note that missing flatfiles will be None in cleaned_data
        key_u, key_p = 'uploaded_flatfile', 'flatfile'
        # add an error message if both flatfile and uploaded flatfile
        # are provided, regardless of whether they are valid or not:
        flatfile_given = cleaned_data.get(key_p, None) or key_p in self.errors
        u_flatfile_given = cleaned_data.get(key_u, None) or key_u in self.errors

        if bool(flatfile_given) == bool(u_flatfile_given):
            # first check when the flatfile is given, and raise
            err_msg = "Please select an existing flatfile or upload one"
            code = 'required'
            if flatfile_given:
                code = 'conflict'
                err_msg = "Please select an existing flatfile or " \
                          "upload one, not both"
            self.add_error(key_p, ValidationError(gettext(err_msg), code=code))
            # Should we add an error also with key 'uploaded_flatfile'? No, because
            # the parameter should not be exposed publicly (we can not send a
            # flatfile in JSON, we need to send a form-multipart request).So:
            # self.add_error(key_u, ValidationError(gettext(err_msg), code=code))
            return cleaned_data  # noo need to further process

        # if no flatfile (name or uploaded) is given in cleaned_data, then the
        # parameter name has been added to errors and we don't need further
        # processing
        if not cleaned_data.get(key_p, None) and not cleaned_data.get(key_u, None):
            return cleaned_data

        if flatfile_given:
            # exception should be raised and sent as 500: don't catch
            p_ff = cleaned_data[key_p]
            dataframe = pd.read_hdf(p_ff.path, key=p_ff.name)
        else:
            u_ff = cleaned_data[key_u]
            try:
                dataframe = read_flatfilefrom_csv_bytes(BytesIO(u_ff))
            except Exception as exc:
                msg = str(exc)
                # provide as key the flatfile param name, becasue so it is
                # exposed to the public:
                self.add_error(key_u, ValidationError(gettext(msg),
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
