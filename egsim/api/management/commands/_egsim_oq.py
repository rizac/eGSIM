"""
Populate the eGSIM database with all OpenQuake data

This command is invoked by `egsim_init.py` and is currently hidden from Django
(because of the leading underscore in the module name)

Created on 6 Apr 2019

@author: riccardo z. (rizac@github.com)
"""
import warnings

import yaml
import inspect
from collections import defaultdict
from typing import Union, Callable, Any

from django.core.management import CommandError
from openquake.baselib.general import DeprecationWarning as OQDeprecationWarning
from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib import imt

from . import EgsimBaseCommand
from ... import models


SUPPORTED_IMTS = (imt.PGA, imt.PGV, imt.SA, imt.PGD, imt.IA, imt.CAV)

FLATFILE_COLUMNS_YAML_PATH = EgsimBaseCommand.data_path("flatfile-columns.yaml")


class Command(EgsimBaseCommand):
    """Class implementing the command functionality"""

    # As help, use the module docstring (until the first empty line):
    help = globals()['__doc__'].split("\n\n")[0]

    def handle(self, *args, **options):
        """Executes the command

        :param args: positional arguments (?). Unclear what should be given
            here. Django doc and Google did not provide much help, source code
            inspection suggests it is here for legacy code (OptParse)
        :param options: any argument (optional or positional), accessible
            as options[<paramname>]. For info see:
            https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/
        """
        # populate db:
        self.printinfo('Populating the database with OpenQuake data (models, '
                       'intensity measures) and flatfile columns metadata')
        imts = populate_imts(**options)
        ffcols, unmapped_ffcols = \
            populate_flatfile_column_metadata()
        (general_errors, unsupported_imt_errors, unknown_params, missing_ffcols) \
            = populate_gsims(imts, ffcols, **options)
        _imtc = models.Imt.objects.count()
        self.printsuccess(f"{_imtc} intensity measure{'' if _imtc == 1 else 's'} "
                          f"saved to database")
        _ffcols = models.FlatfileColumn.objects.count()
        self.printsuccess(f"{_ffcols} flatfile columns and their metadata "
                          f"saved to database")
        if unmapped_ffcols:
            self.printinfo(f"  Unused Flatfile column(s): {', '.join(unmapped_ffcols)}\n"
                           f"  these columns can be removed from:\n"
                           f'  {FLATFILE_COLUMNS_YAML_PATH}')
        _gsimc = models.Gsim.objects.count()
        not_saved = models.GsimWithError.objects.count()
        skipped = len(set(m for mm in missing_ffcols.values() for m in mm))
        discarded = not_saved - skipped
        self.printsuccess(f"{_gsimc} models saved to database, {not_saved} not saved "
                          f"({skipped} skipped, {discarded} discarded)")

        if len(missing_ffcols):
            self.printwarn(f'Skipped models are those requiring any of the following '
                           f'{len(missing_ffcols)} parameter(s) (see database for '
                           f'more details):')
            for param, gsims in missing_ffcols.items():
                self.printwarn(f" - {_param2str(param)} required by {gsims2str(gsims)}")
            self.printwarn(f'  To include a model listed above, re-execute this command '
                           f'after mapping all model parameter(s) to a flatfile column. '
                           f'See instructions in:\n'
                           f'  {FLATFILE_COLUMNS_YAML_PATH}')

        if len(general_errors):
            self.printwarn(f'WARNING: {len(general_errors)} model(s) discarded because '
                           f'of Python errors (e.g., initialization errors, deprecation '
                           f'warnings):\n'
                           f'  {gsims2str(general_errors)}')
        if len(unsupported_imt_errors):
            _models = set(m for mm in unsupported_imt_errors.values() for m in mm)
            self.printwarn(f'WARNING: {len(_models)} model(s) discarded because defined '
                           f'for IMTs not supported by the program:\n')
            for imt, gsims in unsupported_imt_errors.items():
                self.printwarn(f"  - {imt} required by {gsims2str(gsims)}")
            self.printwarn(f'  To include a model listed above, re-execute this command '
                           f'after adding the IMT on top of the file:\n'
                           f'  {__file__}')

        if len(unknown_params):
            _models = set(m for mm in unknown_params.values() for m in mm)
            self.printwarn(f"WARNING: {len(_models)} model(s) discarded because they "
                           f"require any of the following unknown {len(unknown_params)} "
                           f"parameter(s) (see database for more details):")
            for param, gsims in unknown_params.items():
                self.printwarn(f"  - {_param2str(param)} required by {gsims2str(gsims)}")
            self.printwarn(f'  To include a model listed above, re-execute this command '
                           f'after mapping all model parameter(s) to a flatfile column. '
                           f'See instructions in:\n'
                           f'  {FLATFILE_COLUMNS_YAML_PATH}')


def gsims2str(gsim_names: list[str, ...]):
    if len(gsim_names) > 2 + 1:
        # often we have the same model with different suffixes. If we want to display
        # at most 2 models, let's at least provide two distinct names:
        model2 = [m for m in gsim_names if m[:5] != gsim_names[0][:5]]
        # now print those two models and the rest as "and other N models":
        return f'{gsim_names[0]}, {model2[0] if model2 else gsim_names[1]} ' \
               f'and {len(gsim_names)-2} more model{"s" if len(gsim_names)-2> 1 else ""}'
    return ', '.join(gsim_names)


def populate_imts(**options) -> dict[Callable[[Any], imt.IMT], models.Imt]:
    """Write all IMTs from OpenQuake to the db, skipping IMTs which need
    arguments as we do not know how to handle them (except SA)

    :param options: options passed to the Command `handle` method calling this function
    """
    imts = {}
    for imt_func in SUPPORTED_IMTS:
        needs_args = False
        try:
            imt_func()
        except TypeError:
            needs_args = True
        # save to database:
        imts[imt_func] = models.Imt.objects.create(name=imt_func.__name__,
                                                   needs_args=needs_args)
    # last check that everything was written:
    not_written = set(SUPPORTED_IMTS) - set(imts)
    if not_written:
        raise ValueError(f"Could not store {len(not_written)} "
                         f"IMT{'' if len(not_written) == 1 else 's'} "
                         f"on the database: {not_written}")
    return imts


def populate_gsims(imts: dict[Callable[[Any], imt.IMT], models.Imt],
                   ff_cols: dict[str, models.FlatfileColumn], **options)\
        -> tuple[list[str], dict[str, list[str]], dict[str, list[str]], dict[str, list[str]]]:
    """Write all Gsims from OpenQuake to the db

    :param imts: a dict of imt names mapped to the relative db model instance
    :param ff_cols: a dict of OpenQuake parameters (str) mapped to a FlatfileColumn
        db model instance
    :param options: options passed to the Command `handle` method calling this function
    """
    general_errors = []
    unsupported_imt_errors = defaultdict(list)  # imt -> models
    unknown_params = defaultdict(list)  # param -> models (param deliberately excluded)
    missing_ffcols = defaultdict(list)  # ffcol -> models (param not implemented in YAML)
    gsims = []

    for gsim_name, gsim in get_available_gsims().items():
        if inspect.isabstract(gsim):
            continue
        with warnings.catch_warnings():
            warnings.filterwarnings('error')  # raise on warnings
            gsim_warnings = []
            try:
                gsim_inst = gsim()
            except OQDeprecationWarning as warn:
                # treat OpenQuake (OQ) deprecation warnings as errors. Note that
                # the builtin DeprecationWarning is silenced, OQ uses it's own
                store_discarded_gsim(gsim_name, warn, **options)
                general_errors.append(gsim_name)
                continue
            except Warning as warn:
                # A warning has not loaded gsim_inst but raised. Grab the warning
                # but still try to load the Gsim to understand if it can be used
                with warnings.catch_warnings():
                    warnings.filterwarnings('ignore')  # ignore warning temporarily
                    try:
                        gsim_inst = gsim()
                        gsim_warnings.append(str(warn))
                    except Exception as _exc:  # noqa
                        store_discarded_gsim(gsim_name, warn, **options)
                        general_errors.append(gsim_name)
                        continue
            except (OSError, NotImplementedError, KeyError, IndexError,
                    TypeError) as exc:  # MODEL SKIPPING EXCEPTIONS
                store_discarded_gsim(gsim_name, exc, **options)
                general_errors.append(gsim_name)
                continue
            except Exception as _ex:
                errmsg = (f"The model `{gsim_name}()` raised "
                          f"{_ex.__class__.__name__}. You need to handle the "
                          f"exception by fixing the code or, if you think the "
                          f"exception should simply discard the models raising "
                          f"it, add the exception in {__name__} around the "
                          f"line: '# MODEL SKIPPING EXCEPTIONS' "
                          f"(Detailed exception message: {str(_ex)})")
                raise Exception(errmsg) from _ex

        # IMTs. Check now because a Gsim without IMTs can not be saved
        try:
            attname = models.Imt.OQ_ATTNAME
            gsim_imts = getattr(gsim_inst, attname)
            gsim_imts = list(gsim_imts) if hasattr(gsim_imts, '__iter__') else []
            if not gsim_imts:
                raise AttributeError(f"Attribute {attname} empty or not iterable")
            # convert `gsim_imts` from a sequence of OpenQuake imt (Python
            # entity) to the relative db model object:
            u_gsim_imts = [_ for _ in gsim_imts if _ not in imts]
            # ... and that we have imts:
            if len(u_gsim_imts) == len(gsim_imts):
                # convert to strings:
                u_gsim_imts = [getattr(i, "__name__", str(i)) for i in u_gsim_imts]
                for i in u_gsim_imts:
                    unsupported_imt_errors[i].append(gsim_name)
                raise AttributeError(f"Attribute {attname} contains only IMTs "
                                     f"not supported by the program: "
                                     f"{', '.join(u_gsim_imts)}")
            # clear all unsupported imts (gsim_imts will be used later):
            gsim_imts = [imts[_] for _ in gsim_imts if _ in imts]
        except AttributeError as exc:
            store_discarded_gsim(gsim_name, exc, **options)
            continue

        # Gsim flatfile columns from Gsim params (site, rupture, distance)
        gsim_ff_cols = []
        _unknown_params = {}  # param -> error message
        _missing_ffcols = {}  # param -> error message
        # Gsim parameters (site, rupture, distance):
        flatfile_col_category = models.FlatfileColumn.Category
        for attname, ff_category in {
            'REQUIRES_DISTANCES': flatfile_col_category.DISTANCE_MEASURE,
            'REQUIRES_RUPTURE_PARAMETERS': flatfile_col_category.RUPTURE_PARAMETER,
            'REQUIRES_SITES_PARAMETERS': flatfile_col_category.SITE_PARAMETER
        }.items():
            for pname in getattr(gsim_inst, attname, []):
                key = "%s.%s" % (ff_category.name, pname)
                if key not in ff_cols:
                    _unknown_params[key] = f"{_param2str(key)} is unknown"
                    continue
                ff_col = ff_cols[key]
                if ff_col is None:
                    _missing_ffcols[key] = (f"{_param2str(key)} has no "
                                            f"matching flatfile column")
                    continue
                gsim_ff_cols.append(ff_col)

        if _unknown_params:
            for key in _unknown_params:
                unknown_params[key].append(gsim_name)
            _errors = [*_unknown_params.values(), *_missing_ffcols.values()]
            store_discarded_gsim(gsim_name, ", ".join(_errors), **options)
            continue
        elif _missing_ffcols:
            for key in _missing_ffcols:
                missing_ffcols[key].append(gsim_name)
            _errors = _missing_ffcols.values()
            store_discarded_gsim(gsim_name, ", ".join(_errors), **options)
            continue
        elif not gsim_ff_cols:
            general_errors.append(gsim_name)
            store_discarded_gsim(gsim_name,
                                 "No parameter (site, rupture, distance) found",
                                 **options)
            continue

        # pack the N>=0 warning messages into a single msg.
        # If N > 1, prepend each msg with  "1) ...", "2) ...", ...
        gsim_warning = ''
        if len(gsim_warnings) == 1:
            gsim_warning = gsim_warnings[0].strip()
        elif len(gsim_warnings) > 1:
            gsim_warning = " ".join(f"{i}) {_.strip()}" for (i, _)
                                    in enumerate(gsim_warnings, 1))

        # get parameters:
        init_params = {}
        for pn_, pv_ in inspect.signature(gsim_inst.__init__).parameters.items():
            if pv_.kind in (pv_.POSITIONAL_OR_KEYWORD, pv_.KEYWORD_ONLY):
                # exclude *args, **kwargs and positional-only params
                if type(pv_.default) in (int, float, bool, str):
                    init_params[pn_] = pv_.default
                elif pv_.default is not None:
                    pass  # FIXME: warning?
                # Note: if the default is None, but the annotation says int, we
                # might add the parameter anyway, but this it's too
                # complex to manage

        # create (and save) Gsim:
        gsim = models.Gsim.objects.create(name=gsim_name, # noqa
                                          init_parameters=init_params or None,
                                          warning=gsim_warning or None)

        # Many-to-many relationships cannot be set in the __init__, but like this:
        # 1. Set IMTs:
        gsim.imts.set(gsim_imts)
        # 2. Set Gsim parameters:
        gsim.required_flatfile_columns.set(gsim_ff_cols)

        gsims.append(gsim)

    return general_errors, unsupported_imt_errors, unknown_params, missing_ffcols


def populate_flatfile_column_metadata() -> \
        tuple[dict[str, models.FlatfileColumn], list[str]]:
    ffcolumns = read_registered_flatfile_columns()
    ret = {}
    unmatched_ffcols = []
    for ffcol in ffcolumns:
        oq_name = ffcol.get('oq_name', None)
        if not oq_name:
            unmatched_ffcols.append(ffcol['name'])
            continue
        if 'name' not in ffcol:
            ff_col = None
        else:
            ffname = ffcol['name']
            ff_col = models.FlatfileColumn.objects.filter(name=ffname).first()
            if ff_col is None:
                # create (and save) object:
                try:
                    ff_col = models.FlatfileColumn.objects.create(**ffcol)
                except AssertionError as exc:
                    raise CommandError(str(exc))
        full_param_name = f"{ffcol['category'].name}.{oq_name}"
        ret[full_param_name] = ff_col
    return ret, unmatched_ffcols


def read_registered_flatfile_columns() -> list[dict]:
    """Read the registered flatfile columns in `FLATFILE_COLUMNS_YAML_PATH`

    :return: as a list of `dict`s, where each dict holds the flatfile column
        metadata. Important `dict` keys are `name` (the column name) and `oq_name` (the
        OpenQuake property name). Note that any of those could be empty/missing (but not
        both): if `name` is given and not empty, the `dict` can be passed as
        keyword argument(s) to initialize a new `models.FlatfileColumn` instance.
        Otherwise, the dict denotes an OpenQuake property not mapped to any file column,
        e.g., to be deliberately skipped alongside the models requiring that property
    """
    ffcolumns = []
    with open(FLATFILE_COLUMNS_YAML_PATH) as fpt:
        ff_cols = yaml.safe_load(fpt)
        oq_params = ff_cols.pop('openquake_models_parameters')
        for param_type, params in oq_params.items():
            for param_name, ffcol_name in params.items():
                category = models.FlatfileColumn.Category[param_type.upper()]
                ffcolumn = {'oq_name': param_name, 'category': category}
                if ffcol_name:
                    ffcolumn['name'] = ffcol_name
                    props = ff_cols.pop(ffcol_name) or {}
                    ffcolumn['help'] = props.pop('help', '')
                    ffcolumn['properties'] = props
                ffcolumns.append(ffcolumn)
    for ffcol_name, ffcolumn in ff_cols.items():
        help_ = ffcolumn.pop('help', '')
        ffcolumns.append({
            'name': ffcol_name,
            'properties': ffcolumn,
            'help': help_
        })
    return ffcolumns


def store_discarded_gsim(gsim_name: str, error: Union[str, Exception],
                         **options):
    """Creates an error from the given entity type (e.g. `DB_ENTITY.GSIM`) and
    key (e.g., the Gsim class name) and saves it to the database.
    Note: if `error_type` is missing or None it is set as:
        1. `error.__class__.__name__` if `error` is an `Exception`
        2. "Error" otherwise
    :param options: options passed to the Command `handle` method calling this function
    """
    if isinstance(error, Exception):
        error_type, error_msg = error.__class__.__name__, str(error)
    else:
        error_type, error_msg = 'Error', str(error)

    models.GsimWithError.objects.create(name=gsim_name, error_type=error_type,
                                        error_message=error_msg)


def _param2str(param: str):
    """Makes `param` human readable, e.g. 'SITE_PARAMETER.PHV' into:
    'Site parameter "PHV"

    :param param: a model parameter name, in the format `category.name`,
        e.g. 'SITE_PARAMETER.PHV' (`category` is one of the names of the enum
        `models.FlatfileColumn.Ctegory`
    """
    category, name = param.split(".", 1)
    category = category.replace('_', ' ').capitalize()
    return f'{category} "{name}"'
