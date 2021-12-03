"""
(Re)populate the eGSIM database with all OpenQuake data

This command is invoked by `egsim_init.py` and is currently hidden from Django
(beacuse of the leading underscore in the module name)

Created on 6 Apr 2019

@author: riccardo
"""
import warnings
import inspect
from collections import defaultdict
from typing import Union
from enum import Enum

from openquake.baselib.general import (DeprecationWarning as
                                       OQDeprecationWarning)
from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib import imt

from ..gsim_params import (read_gsim_params, DEFAULT_FILE_PATH as model_params_filepath)
from . import EgsimBaseCommand
from ... import models


SUPPORTED_IMTS = (imt.PGA, imt.PGV, imt.SA, imt.PGD, imt.IA, imt.CAV)


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
        self.printinfo('Populating DB with OpenQuake data:')
        imts = populate_imts()
        model_params = read_gsim_params()
        _, missing_params, unused_params = populate_gsims(imts, model_params)

        _imtc = models.Imt.objects.count()  # noqa
        _imt = 'Imt' if _imtc == 1 else 'Imts'
        self.printsuccess('%d %s written' % (_imtc, _imt))

        _gsimc = models.Gsim.objects.count()  # noqa
        _gsim = 'Gsim' if _gsimc == 1 else 'Gsims'
        self.printsuccess('%d %s written, %d skipped' %
                          (_gsimc, _gsim,
                           models.GsimWithError.objects.count()))  # noqa

        self.printinfo('A Gsim might be skipped for various reasons, e.g.:')
        self.printinfo(' - initialization errors')
        self.printinfo(' - not defined for any supported Imt')
        self.printinfo(' - requiring parameters that have no '
                       'associated flatfile name in ' + model_params_filepath)

        if unused_params:
            _prm = 'parameter' if len(unused_params) == 1 else 'parameters'
            verb = 'is' if len(unused_params) == 1 else 'are'
            self.printinfo('   (note: %d %s in the yaml file %s not required by any '
                           'written Gsim: %s' % (len(unused_params), _prm, verb,
                                                 ", ".join(unused_params)))

        if missing_params:
            _prms = 'parameter' if len(missing_params) == 1 else 'parameters'
            self.printwarn('WARNING:')
            self.printwarn(' Some Gsims were skipped because they '
                           'require the following unknown %d %s (edit '
                           'yaml file above if needed. See details in the file): ' %
                           (len(missing_params), _prms))
            for param, gsims in missing_params.items():
                gsim_ = 'Gsim' if len(gsims) == 1 else 'Gsims'
                self.printwarn(" - %s required by %d skipped %s" %
                               (_param2str(param), len(gsims), gsim_))


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
        raise ValueError('Could not store %d IMT(s) on the database: %s' %
                         (len(not_written), not_written))
    return imts


def populate_gsims(imts: dict[imt.IMT, models.Imt], model_params: dict[str, dict])\
        -> tuple[list[models.Gsim], dict[str, list[str]], set[str]]:
    """Write all Gsims from OpenQuake to the db

    :param imts: a dict of imt names mapped to the relative db model instance
    :param model_params: the dict of Gsim parameters mapped to their properties,
        as registered in the internal YAML file
    """
    gsims = []

    saved_params = {}  # paramname -> flatfilename
    missing_params = defaultdict(list)

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
                        continue
            except (OSError, NotImplementedError, KeyError, IndexError,
                    TypeError) as exc:
                # NOTE: ADD HERE THE EXCEPTIONS THAT YOU WANT TO JUST REPORT.
                store_gsim_error(gsim_name, exc)
                continue
            except Exception as _ex:
                # IMPORTANT For developers: if we are here something unexpected
                # happened. Therefore, inspect the traceback and - if nothing
                # critical is detected - skip the Gsim raising this exception
                # by adding the latter to the `except` clause above. Otherwise,
                # fix the problem
                errmsg = ("`%s()` raised %s which should be added in module %s, "
                          "at the line of code reading \"except (OSError, ...\"  "
                          "(original err msg: %s)") % \
                         (gsim_name, _ex.__class__.__name__, __name__, str(_ex))
                raise Exception(errmsg) from _ex

            # IMTs. Check now because a Gsim without IMTs can not be saved
            try:
                attname = models.Imt.OQ_ATTNAME
                gsim_imts = getattr(gsim_inst, attname)
                if not hasattr(gsim_imts, '__iter__'):
                    # gsim_imts is not iterable, raise (caught below):
                    # raise AttributeError('%s.%s not iterable' %
                    #                      (gsim_name, attname))
                    raise AttributeError('Attribute %s not iterable' % attname)
                # convert `gsim_imts` from a sequence of OpenQuake imt (Python
                # entity) to the relative db model object:
                gsim_imts = [imts[_] for _ in gsim_imts if _ in imts]
                # ... and that we have imts:
                if not gsim_imts:
                    # raise AttributeError(('%s.%s has no IMT supported by the '
                    #                       'program') % (gsim_name, attname))
                    raise AttributeError(('Attribute %s has no IMT supported by the '
                                          'program') % attname)
            except AttributeError as exc:
                store_gsim_error(gsim_name, exc)
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
                            raise ValueError('%s is unknown' % _param2str(key))

                        if key not in saved_params:
                            props = model_params[key] or {}
                            ffname = props.pop('flatfile_name', None)
                            if ffname is None:
                                raise ValueError('%s has no matching '
                                                 'flatfile column' % _param2str(key))
                            # save to model
                            help_ = props.pop('help', '')
                            category = attname2category[attname]
                            # create (and save) object:
                            models.FlatfileColumn.objects.create(name=ffname,
                                                                 help=help_,
                                                                 properties=props,
                                                                 category=category,
                                                                 oq_name=pname)
                            saved_params[key] = ffname

                        db_p = models.FlatfileColumn.objects.\
                            get(name=saved_params[key])
                        gsim_db_params.append(db_p)

                if not gsim_db_params:
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
                gsim_warning = " ".join('%d) %s' % (i, _.strip())
                                        for (i, _) in enumerate(gsim_warnings, 1))

            # Get Trt attribute (should silently fail in case):
            trt = getattr(gsim_inst, models.GsimTrt.OQ_ATTNAME, None)
            trt_s = trt.name if isinstance(trt, Enum) else str(trt)
            gsim_trt = trt if trt is None else \
                models.GsimTrt.objects.get_or_create(name=trt_s)[0]  # noqa

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
            gsim = models.Gsim.objects.create(name=gsim_name, trt=gsim_trt,  # noqa
                                              init_parameters=init_params or None,
                                              warning=gsim_warning or None)

            # Many-to-many relationships cannot be set in the __init__, but like this:
            # 1. Set IMTs:
            gsim.imts.set(gsim_imts)
            # 2. Set Gsim parameters:
            gsim.required_flatfile_columns.set(gsim_db_params)

            gsims.append(gsim)

    unused_params = set(model_params) - set(saved_params)
    return gsims, missing_params, unused_params


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
    'REQUIRES_DISTANCES' : models.FlatfileColumn.CATEGORY.DISTANCE_MEASURE,
    'REQUIRES_RUPTURE_PARAMETERS': models.FlatfileColumn.CATEGORY.RUPTURE_PARAMETER,
    'REQUIRES_SITES_PARAMETERS': models.FlatfileColumn.CATEGORY.SITE_PARAMETER
}


def _param2str(param):
    """Converts a model parameter key (as read from the YAML file)
    into a human readable name"""
    attname, pname = param.split(".", 1)
    categ = attname2category[attname]
    return categ.name.replace('_', ' ').capitalize() + \
        ' "%s" (found in Gsim attribute `%s`)' % (pname, attname)
