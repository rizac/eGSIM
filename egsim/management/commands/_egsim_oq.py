"""
(Re)populate the eGSIM database with all GSIMs, IMTs (and their relations)
implemented in the currently used version of OpenQuake.

This command is invoked by `egsim_init.py` and exists only because of legacy code:
as there is no point in executing this command alone (all existing data must be
deleted beforehand, and thus some deleted data must be recreated afterwards),
for simplicity it has been turned it into a hidden command via the lading "_"
in its name: we can call this command via Django `call_command` but we can not
see it or invoke from the terminal

Created on 6 Apr 2019

@author: riccardo
"""
import warnings
import inspect

from typing import Union

from openquake.baselib.general import (DeprecationWarning as
                                       OQDeprecationWarning)
from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib import imt

from egsim.management.commands._utils import EgsimBaseCommand, get_command_datadir
import egsim.models as models


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

        self.printinfo(' > Intensity measure types (Imt)')
        imts = populate_imts()

        self.printinfo(' > Ground shaking intensity models (Gsim)')
        populate_gsims(imts)
        self.printsuccess('   %d written, %d skipped due to errors' %
                          (models.Gsim.objects.count(),
                           models.GsimWithError.objects.count()))  # noqa

        unknown_instances = set_flatfile_columns()
        # gsim_names = Gsim.objects.all()  # noqa
        # gsim_names = gsim_names.values_list('name', flat=True)
        if unknown_instances:
            self.printwarn(
                '\nWARNING: %d attributes are required for some Gsim in '
                'OpenQuake code, but do not have a mapping to any flatfile '
                'column. This is not critical for the program it is just for '
                'your information in case there is something to fix due to new '
                'attributes (e.g., new flatfile column definition)' %
                len(unknown_instances))
            self.printwarn('List of attributes:')
            for instance in unknown_instances:
                gsims = [_.name for _ in instance.gsims.all()]
                gsim_str = (str(_) for _ in gsims) if len(gsims) <= 2 else \
                    [str(gsims[0]), "other %d Gsims" % (len(gsims) - 1)]
                gsim_str = '(defined for "%s")' % (" and ".join(gsim_str))
                attname = instance.OQ_ATTNAME + '.' + instance.name
                self.printwarn('%s %s' % (attname, gsim_str))


_SUPPORTED_IMTS = (imt.PGA, imt.PGV, imt.SA, imt.PGD, imt.IA, imt.CAV)


def populate_imts() -> dict[type(_SUPPORTED_IMTS[0]), models.Imt]:
    """Write all IMTs from OpenQuake to the db, skipping IMTs which need
    arguments as we do not know how to handle them (except SA)
    """
    # `create` below creates and saves an object
    # https://docs.djangoproject.com/en/3.1/ref/models/querysets/#django.db.models.query.QuerySet.create
    imts = {}
    for imt_func in _SUPPORTED_IMTS:
        needs_args = False
        try:
            imt_func()
        except TypeError:
            needs_args = True
        imts[imt_func] = models.Imt.objects.create(name=imt_func.__name__,  # noqa
                                                   needs_args=needs_args)
    # last check that everything was written:
    not_written = set(_SUPPORTED_IMTS) - set(imts)
    if not_written:
        raise ValueError('Could not store %d IMT(s) on the database: %s' %
                         (len(not_written), not_written))
    return imts


def populate_gsims(imts: dict[imt.IMT, models.Imt]) -> list[models.Gsim]:
    """Write all Gsims from OpenQuake to the db

    :param imts: a dict of imt names mapped to the relative db model instance
    """
    # `create` below creates and saves an object
    # https://docs.djangoproject.com/en/3.1/ref/models/querysets/#django.db.models.query.QuerySet.create
    gsims = []

    with warnings.catch_warnings():
        # Catch warnings as if they were exceptions, and skip deprecation w.
        # https://stackoverflow.com/a/30368735
        warnings.filterwarnings('error')  # raises every time, not only 1st
        for gsim_name, gsim in get_available_gsims().items():
            if inspect.isabstract(gsim):
                continue
            gsim_warnings = []
            needs_args = False

            try:
                gsim_inst = gsim()
            except OQDeprecationWarning as warn:
                # treat OpenQuake (OQ) deprecation warnings as errors. Note that
                # the builtin DeprecationWarning is silenced, OQ uses it's own
                store_gsim_error(gsim_name, warn)
                continue
            except Warning as warn:
                gsim_warnings.append(str(warn))
            except TypeError:
                gsim_inst = gsim
                needs_args = True
            except (OSError, NotImplementedError, KeyError, IndexError) as exc:
                # NOTE: ADD HERE THE EXCEPTIONS THAT YOU WANT TO JUST REPORT.
                store_gsim_error(gsim_name, exc)
                continue
            except Exception as _ex:
                # IMPORTANT For developers: if we are here something unexpected
                # happened. Therefore, inspect the traceback and - if nothing
                # critical is detected - skip the Gsim raising this exception
                # by adding the latter to the `except` clause above. Otherwise,
                # fix the problem
                errmsg = ("Attempt to initialize %s raised %s which is "
                          "not handled in module %s (original err msg: %s)") % \
                         (str(gsim), _ex.__class__.__name__, __name__, str(_ex))
                raise Exception(errmsg) from _ex

            # IMTs. Check now because a Gsim without IMTs can not be saved
            try:
                attname = models.Imt.OQ_ATTNAME
                gsim_imts = getattr(gsim_inst, attname)
                if not hasattr(gsim_imts, '__iter__'):
                    # gsim_imts is not iterable, raise (caught below):
                    raise AttributeError('%s.%s not iterable' %
                                         (gsim_name, attname))
                # convert `gsim_imts` from a sequence of OpenQuake imt (Python
                # functions) to the relative db model object:
                gsim_imts = [imts[_] for _ in gsim_imts if _ in imts]
                # ... and that we have imts:
                if not gsim_imts:
                    raise AttributeError(('%s.%s has no IMT supported by the '
                                          'program') % (gsim_name, attname))
            except AttributeError as exc:
                store_gsim_error(gsim_name, exc)
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
            gsim_trt = trt if trt is None else \
                models.GsimTrt.objects.get_or_create(name=str(trt))[0]  # noqa

            # Save Gsim:
            gsim = models.Gsim.objects.create(name=gsim_name, trt=gsim_trt,
                                              warning=gsim_warning or None,
                                              needs_args=needs_args)
            # Seet IMTs:
            gsim.imts.set(gsim_imts)

            # Other secondary gsim attributes (should silently fail in case):
            objs = [models.GsimAttribute.objects.get_or_create(name=str(_))[0]  # noqa
                    for _ in getattr(gsim_inst, models.GsimAttribute.OQ_ATTNAME, [])]
            gsim.attributes.set(objs)

            objs = [models.GsimDistance.objects.get_or_create(name=str(_))[0]  # noqa
                    for _ in getattr(gsim_inst, models.GsimDistance.OQ_ATTNAME, [])]
            gsim.distances.set(objs)

            objs = [models.GsimSitesParam.objects.get_or_create(name=str(_))[0]  # noqa
                    for _ in getattr(gsim_inst, models.GsimSitesParam.OQ_ATTNAME, [])]
            gsim.sites_parameters.set(objs)

            objs = [models.GsimRuptureParam.objects.get_or_create(name=str(_))[0]  # noqa
                    for _ in getattr(gsim_inst, models.GsimRuptureParam.OQ_ATTNAME, [])]
            gsim.rupture_parameters.set(objs)

            gsims.append(gsim)

    return gsims


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

    models.GsimWithError.objects.create(name=gsim_name, error_type=error_type,
                                        error_message=error_msg)


def set_flatfile_columns():
    not_found = []
    for mod_name in dir(models):
        model = getattr(models, mod_name)
        try:
            if not issubclass(model, models._ModelWithFlatfileMapping) or \
                    model._meta.abstract:
                raise TypeError()
        except TypeError:  # raised from above, or if model is not a Python class
            continue
        for instance in model.objects.all():
            if instance.name not in model.__flatfile_mapping__:
                not_found.append(instance)
                continue
            flatfile_col = model.__flatfile_mapping__[instance.name]
            if flatfile_col:
                instance.flatfile_column = flatfile_col
                instance.save()
    return not_found

