"""
(Re)populate the eGSIM database with all OpenQuake data

This command is invoked by `egsim_init.py` and is currently hidden from Django
(because of the leading underscore in the module name)

Created on 6 Apr 2019

@author: riccardo z. (rizac@github.com)
"""
import warnings
import os
import yaml
import inspect
from collections import defaultdict
from typing import Union, Iterable

from django.core.management import CommandError
from openquake.baselib.general import (DeprecationWarning as
                                       OQDeprecationWarning)
from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib import imt

from . import EgsimBaseCommand
from ... import models


SUPPORTED_IMTS = (imt.PGA, imt.PGV, imt.SA, imt.PGD, imt.IA, imt.CAV)

GSIM_PARAMS_YAML_PATH = EgsimBaseCommand.data_path("gsim_params.yaml")


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

        imts = populate_imts()
        (general_errors, unsupported_imt_errors, excluded_params, missing_params) \
            = populate_gsims(imts)

        _imtc = models.Imt.objects.count()  # noqa
        self.printsuccess(f"{_imtc} intensity measure{'' if _imtc == 1 else 's'} "
                          f"saved to database")
        _ffcols = models.FlatfileColumn.objects.count()
        self.printsuccess(f"{_ffcols} flatfile columns and their metadata "
                          f"saved to database")
        _gsimc = models.Gsim.objects.count()  # noqa
        not_saved = models.GsimWithError.objects.count()  # noqa
        skipped = sum(len(_) for _ in excluded_params.values())
        discarded = not_saved - skipped
        self.printsuccess(f"{_gsimc} models saved to database, {not_saved} not saved "
                          f"({skipped} skipped, {discarded} discarded)")

        if len(excluded_params):
            self.printwarn(f'Skipped models are those requiring any of the following '
                           f'{len(excluded_params)} parameter(s) (see database for '
                           f'more details):')
            for param, gsims in excluded_params.items():
                self.printwarn(f" - {_param2str(param)} required by {models2str(gsims)}")
            self.printwarn(f'  To include a model listed above, re-execute this command '
                           f'after mapping all model parameter(s) to a flatfile column '
                           f'in the file:\n'
                           f'  {GSIM_PARAMS_YAML_PATH}')

        if len(general_errors):
            self.printwarn(f'WARNING: {len(general_errors)} model(s) discarded because '
                           f'of Python errors (e.g., initialization errors, deprecation '
                           f'warnings):\n'
                           f'  {models2str(general_errors)}')
        if len(unsupported_imt_errors):
            self.printwarn(f'WARNING: {len(unsupported_imt_errors)} model(s) discarded '
                           f'because defined for IMTs not supported by the program:\n'
                           f'  {models2str(unsupported_imt_errors)}')

        if len(missing_params):
            self.printwarn(f"WARNING: {sum(len(_) for _ in missing_params.values())} "
                           f"model(s) discarded because they require any of the "
                           f"following unknown {len(missing_params)} parameter(s) "
                           f"(see database for more details):")
            for param, gsims in missing_params.items():
                self.printwarn(f"  - {_param2str(param)} required by {models2str(gsims)}")
            self.printwarn(f'  To include a model listed above, re-execute this command '
                           f'after mapping all model parameter(s) to a flatfile column '
                           f'in the file:\n'
                           f'  {GSIM_PARAMS_YAML_PATH}')


def models2str(models: list[str, ...]):
    if len(models) > 2 + 1:
        # often we have the same model with different suffixes. If we want to display
        # at most 2 models, let's at least provide two distinct names:
        model2 = [m for m in models if m[:5] != models[0][:5]]
        # now print those two models and the rest as "and other N models":
        return f'{models[0]}, {model2[0] if model2 else models[1]} ' \
               f'and {len(models)-2} more model{"s" if len(models)-2> 1 else ""}'
    return ', '.join(models)


def populate_imts() -> dict[imt.IMT, models.Imt]:
    """Write all IMTs from OpenQuake to the db, skipping IMTs which need
    arguments as we do not know how to handle them (except SA)
    """
    imts = {}
    for imt_func in SUPPORTED_IMTS:
        needs_args = False
        try:
            imt_func()
        except TypeError:
            needs_args = True
        # Create and save:
        imts[imt_func] = models.Imt.objects.create(name=imt_func.__name__,  # noqa
                                                   needs_args=needs_args)
    # last check that everything was written:
    not_written = set(SUPPORTED_IMTS) - set(imts)
    if not_written:
        raise ValueError(f"Could not store {len(not_written)} "
                         f"IMT{'' if len(not_written) == 1 else 's'} "
                         f"on the database: {not_written}")
    return imts


def populate_gsims(imts: dict[imt.IMT, models.Imt])\
        -> tuple[list[str], list[str], dict[str, list[str]], dict[str, list[str]]]:
    """Write all Gsims from OpenQuake to the db

    :param imts: a dict of imt names mapped to the relative db model instance
    """
    general_errors = []
    unsupported_imt_errors = []
    excluded_params = defaultdict(list)  # model params deliberately excluded (no flatfile col)
    missing_params = defaultdict(list)  # model params missing (not implemented in YAML)
    gsims = []
    # read GSIM parameters:
    model_params = read_gsim_params()
    saved_params = {}  # paramname -> flatfilename
    with warnings.catch_warnings():
        warnings.filterwarnings('error')  # raise on warnings
        for gsim_name, gsim in get_available_gsims().items():
            if inspect.isabstract(gsim):
                continue
            gsim_warnings = []
            try:
                gsim_inst = gsim()
            except OQDeprecationWarning as warn:
                # treat OpenQuake (OQ) deprecation warnings as errors. Note that
                # the builtin DeprecationWarning is silenced, OQ uses it's own
                store_gsim_error(gsim_name, warn)
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
                        store_gsim_error(gsim_name, warn)
                        general_errors.append(gsim_name)
                        continue
            except (OSError, NotImplementedError, KeyError, IndexError,
                    TypeError) as exc:  # MODEL SKIPPING EXCEPTIONS
                store_gsim_error(gsim_name, exc)
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
                if not hasattr(gsim_imts, '__iter__'):
                    # gsim_imts is not iterable, raise (caught below):
                    # raise AttributeError('%s.%s not iterable' %
                    #                      (gsim_name, attname))
                    raise AttributeError(f"Attribute {attname} not iterable")
                # convert `gsim_imts` from a sequence of OpenQuake imt (Python
                # entity) to the relative db model object:
                gsim_imts = [imts[_] for _ in gsim_imts if _ in imts]
                # ... and that we have imts:
                if not gsim_imts:
                    raise AttributeError(f"Attribute {attname} has no IMT "
                                         f"supported by the program")
            except AttributeError as exc:
                store_gsim_error(gsim_name, exc)
                unsupported_imt_errors.append(gsim_name)
                continue

            # Parameters. check now because a Gsim with unknown parameters
            # OR with no corresponding flatfile name cannot be saved
            gsim_db_params = []
            try:
                # Gsim parameters (site, rupture, distance):
                for attname in attname2category:
                    for pname in getattr(gsim_inst, attname, []):

                        key = "%s.%s" % (attname, pname)
                        if key not in model_params:
                            missing_params[key].append(gsim_name)
                            # this exception is not exiting (see below):
                            raise ValueError(f"{_param2str(key)} is unknown")

                        if key not in saved_params:
                            props = model_params[key] or {}
                            ffname = props.pop('flatfile_name', None)
                            if ffname is None:
                                excluded_params[key].append(gsim_name)
                                # this exception is not exiting (see below):
                                raise ValueError(f"{_param2str(key)} has no "
                                                 f"matching flatfile column")
                            # save to model
                            help_ = props.pop('help', '')
                            category = attname2category[attname]
                            # create (and save) object:
                            try:
                                models.FlatfileColumn.objects.create(name=ffname,
                                                                     help=help_,
                                                                     properties=props,
                                                                     category=category,
                                                                     oq_name=pname)
                            except AssertionError as exc:
                                raise CommandError(str(exc))
                            saved_params[key] = ffname

                        db_p = models.FlatfileColumn.objects.\
                            get(name=saved_params[key])
                        gsim_db_params.append(db_p)

                if not gsim_db_params:
                    general_errors.append(gsim_name)
                    raise ValueError("No parameter (site, rupture, distance) found")

            except ValueError as verr:
                store_gsim_error(gsim_name, verr)
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
            gsim.required_flatfile_columns.set(gsim_db_params)

            gsims.append(gsim)

    return general_errors, unsupported_imt_errors, excluded_params, missing_params


def read_gsim_params() -> dict[str, dict]:
    """Returns the GSIM YAML param `gsim_params.yaml into a dict[str, dict]"""
    model_params = {}
    with open(GSIM_PARAMS_YAML_PATH) as fpt:
        root_dict = yaml.safe_load(fpt)
        for param_type, params in root_dict.items():
            for param_name, props in params.items():
                model_params[f'{param_type}.{param_name}'] = props
    return model_params


def store_gsim_error(gsim_name: str, error: Union[str, Exception]):
    """Creates an error from the given entity type (e.g. `DB_ENTITY.GSIM`) and
    key (e.g., the Gsim class name) and saves it to the database.
    Note: if `error_type` is missing or None it is set as:
        1. `error.__class__.__name__` if `error` is an `Exception`
        2. "Error" otherwise
    """
    if isinstance(error, Exception):
        error_type, error_msg = error.__class__.__name__, str(error)
    else:
        error_type, error_msg = 'Error', str(error)

    models.GsimWithError.objects.create(name=gsim_name, error_type=error_type,  # noqa
                                        error_message=error_msg)


# Maps Gsim attribute names to the relative Flatfile category (IntEnum):
attname2category = {
    'REQUIRES_DISTANCES': models.FlatfileColumn.Category.DISTANCE_MEASURE,
    'REQUIRES_RUPTURE_PARAMETERS': models.FlatfileColumn.Category.RUPTURE_PARAMETER,
    'REQUIRES_SITES_PARAMETERS': models.FlatfileColumn.Category.SITE_PARAMETER
}


def _param2str(param: str):
    """Makes `param` human readable, e.g. 'REQUIRES_DISTANCES.rcdpp' into:
    'Distance measure "rcdpp" (found in Gsim attribute `REQUIRES_DISTANCES`)'

    :param param: a model parameter name, in the format `category.name`,
        e.g. 'REQUIRES_DISTANCES.rcdpp' (`category` is one of the keys of
        `atrname2category`)
    """
    attname, pname = param.split(".", 1)
    categ = attname2category[attname]
    return categ.name.replace('_', ' ').capitalize() + \
        f' "{pname}"' # (found in Gsim attribute `{attname}`)'
