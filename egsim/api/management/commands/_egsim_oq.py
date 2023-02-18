"""
Populate the eGSIM database with all OpenQuake data

This command is invoked by `egsim_init.py` and is currently hidden from Django
(because of the leading underscore in the module name)

Created on 6 Apr 2019

@author: riccardo z. (rizac@github.com)
"""
import warnings

from os.path import abspath, dirname, join, isfile
import inspect
from collections import defaultdict
from typing import Union

from openquake.baselib.general import DeprecationWarning as OQDeprecationWarning
from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib import imt

from . import EgsimBaseCommand
from ... import models
from egsim.smtk import flatfile


FLATFILE_COLUMNS_YAML_PATH = abspath(join(dirname(dirname(dirname(dirname(__file__)))),
                                          "smtk", "flatfile-columns.yaml"))

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
        assert isfile(FLATFILE_COLUMNS_YAML_PATH), f"{FLATFILE_COLUMNS_YAML_PATH} " \
                                                   f"does not denote an existing file"
        # populate db:
        self.printinfo('Populating the database with OpenQuake data (models, '
                       'intensity measures) and flatfile columns metadata')
        ffcols = populate_flatfile_column_metadata()
        imts = populate_imts(ffcols, **options)
        (general_errors, unsupported_imt_errors, unknown_params) = \
            populate_gsims(imts, ffcols, **options)
        _imtc = models.Imt.objects.count()
        self.printsuccess(f"{_imtc} intensity measure{'' if _imtc == 1 else 's'} "
                          f"saved to database")
        _ffcols = models.FlatfileColumn.objects.count()
        self.printsuccess(f"{_ffcols} flatfile columns and their metadata "
                          f"saved to database")
        _gsimc = models.Gsim.objects.count()
        not_saved = models.GsimWithError.objects.count()

        # discarded = not_saved - skipped
        self.printsuccess(f"{_gsimc} models saved to database, {not_saved} discarded "
                          f"(not saved)")

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
                           f'after adding the IMT as flatfile column in the file:\n'
                           f'  {FLATFILE_COLUMNS_YAML_PATH}')

        if len(unknown_params):
            _models = set(m for mm in unknown_params.values() for m in mm)
            self.printwarn(f"WARNING: {len(_models)} model(s) discarded because they "
                           f"require any of the following unknown {len(unknown_params)} "
                           f"parameter(s) (see database for more details):")
            for param, gsims in unknown_params.items():
                self.printwarn(f"  - {_param2str(*param)} required by "
                               f"{gsims2str(gsims)}")
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


def populate_flatfile_column_metadata() -> list[models.FlatfileColumn]:
    ffcolumns = flatfile.read_registered_flatfile_columns_metadata()
    ret = {}
    for name, column_metadata in ffcolumns.items():
        ff_col = models.FlatfileColumn.objects.filter(name=name).first()
        if ff_col is None: # create (and save) object:
            kwarg = column_metadata.as_dict()
            data_props = {k :kwarg.pop(k)
                          for k in ('dtype', 'bounds', 'default', 'required')
                          if k in kwarg}
            ret[name] = \
                models.FlatfileColumn.objects.create(name=name, **kwarg,
                                                     data_properties=data_props)
    return list(ret.values())


def populate_imts(ffcols: list[models.FlatfileColumn],
                  **options) -> dict[str, models.Imt]:
    """Write all IMTs from OpenQuake to the db from the given dict of flatfile.Column
    objects

    :param ffcols: a dict of flatfile column names mapped to their flatfile.Column object
    :param options: options passed to the Command `handle` method calling this function
    """
    names = [c.name for c in ffcols
             if c.category == flatfile.ColumnMetadata.Category.imt]
    imts = {}
    for imt_name in names:
        ok = callable(getattr(imt, imt_name, None))
        if not ok:
            raise ValueError(f"{imt_name} does not denote a valid OpenQuake IMT")
        needs_args = False
        try:
            getattr(imt, imt_name)()
        except TypeError:
            needs_args = True
        # save to database:
        imts[imt_name] = models.Imt.objects.create(name=imt_name, needs_args=needs_args)
    return imts


def populate_gsims(imts: dict[str, models.Imt],
                   ff_cols: list[models.FlatfileColumn],
                   **options)\
        -> tuple[list[str], dict[str, list[str]], dict[str, list[str]]]:
    """Write all Gsims from OpenQuake to the db

    :param imts: a dict of imt names mapped to the relative db model instance
    :param ff_cols: a dict of OpenQuake parameters (str) mapped to a FlatfileColumn
        db model instance
    :param options: options passed to the Command `handle` method calling this function
    """
    general_errors = []
    unsupported_imt_errors = defaultdict(list)  # imt -> models
    unknown_params = defaultdict(list)  # param -> models (param deliberately excluded)
    gsims = []
    oq_param2ff_col = {(c.category, c.oq_name): c for c in ff_cols if c.oq_name}
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
            gsim_imts = getattr(gsim_inst, attname, None)
            if not hasattr(gsim_imts, '__iter__'):
                raise AttributeError(f"Attribute {attname} empty or not iterable")
            gsim_imts = [i.__name__ for i in gsim_imts]  # convert imts to str
            gsim_imts_to_remove = [_ for _ in gsim_imts if _ not in imts]
            if len(gsim_imts_to_remove) == len(gsim_imts):
                # convert to strings:
                for i in gsim_imts:
                    unsupported_imt_errors[i].append(gsim_name)
                raise AttributeError(f"Attribute {attname} contains only IMTs "
                                     f"not supported by the program: "
                                     f"{', '.join(gsim_imts)}")
            # set gsim_imts as a list of model instances:
            gsim_imts = [imts[_] for _ in gsim_imts if _ in imts]
        except AttributeError as exc:
            store_discarded_gsim(gsim_name, exc, **options)
            continue

        # Gsim flatfile columns from Gsim params (site, rupture, distance)
        gsim_ff_cols = []
        _unknown_params = {}  # param -> error message
        # Gsim parameters (site, rupture, distance):
        for attname, ff_category in {
            'REQUIRES_DISTANCES': flatfile.ColumnMetadata.Category.distance_measure,
            'REQUIRES_RUPTURE_PARAMETERS': flatfile.ColumnMetadata.Category.rupture_parameter,
            'REQUIRES_SITES_PARAMETERS': flatfile.ColumnMetadata.Category.site_parameter
        }.items():
            for pname in getattr(gsim_inst, attname, []):
                key = (ff_category, pname)
                if key not in oq_param2ff_col:
                    _unknown_params[key] = f"{_param2str(*key)} is unknown"
                else:
                    gsim_ff_cols.append(oq_param2ff_col[key])

        if _unknown_params:
            for key in _unknown_params:
                unknown_params[key].append(gsim_name)
            store_discarded_gsim(gsim_name, ", ".join(_unknown_params.values()),
                                 **options)
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

    return general_errors, unsupported_imt_errors, unknown_params


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


def _param2str(category: flatfile.ColumnMetadata.Category, name: str):
    """Makes `param` and its `category` human readable, e.g. (SITE_PARAMETER, 'PHV')
    into: 'Site parameter "PHV"'
    """
    category = category.name.replace('_', ' ').capitalize()
    return f'{category} "{name}"'
