"""
Module for initializing the database with OpenQuake data

For info see:
https://django.readthedocs.io/en/2.0.x/howto/custom-management-commands.html

Created on 6 Apr 2019

@author: riccardo
"""
import os
import warnings
import inspect
from collections import defaultdict
from typing import Dict, Union

from django.db.utils import OperationalError
from django.core.management.base import BaseCommand, CommandError
from openquake.baselib.general import (DeprecationWarning as
                                       OQDeprecationWarning)
from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib.imt import registry as hazardlib_imt_registry, IMT
from openquake.hazardlib.const import TRT
from openquake.hazardlib import imt

from egsim.management.commands._utils import EgsimBaseCommand
from egsim.models import Gsim, Imt, Trt, Error, empty_all, DB_ENTITY
from egsim.core.utils import OQ, GSIM_REQUIRED_ATTRS


class Command(EgsimBaseCommand):
    """Command to initialize the db: python manage.py oq2db
    """

    # The formatting of the help text below (e.g. newlines) will be preserved
    # in the terminal output. All text after "Notes:" will be skipped from the
    # help of the wrapper/main command 'initdb'
    help = "\n". join([
        'Initializes and populates eGSIM database with all GSIMs, IMTs and TRTs',
        'implemented in version of OpenQuake used by the program.',
        'Notes:',
        ' - GSIM: Ground Shaking Intensity Model',
        ' - IMT: Intensity Measure Type',
        ' - TRT: Tectonic Region Type',
        ' - All database tables will be emptied and rewritten'
    ])

    def handle(self, *args, **options):
        """Executes the command

        :param args: positional arguments (?). Unclear what should be given
            here. Django doc and Google did not provide much help, source code
            inspection suggests it is here for legacy code (OptParse)
        :param options: any argument (optional or positional), accessible
            as options[<paramname>]. For info see:
            https://docs.djangoproject.com/en/2.2/howto/custom-management-commands/
        """
        # delete db:
        try:
            self.printinfo("Emptying DB Tables")
            empty_all()
        except OperationalError as no_db:
            # (CommandError is an Exception just handled by
            # Django to print nicely the error on the terminal)
            raise CommandError('%s.\nDid you create the db first?\n(for '
                               'info see: https://docs.djangoproject.'
                               'com/en/2.3/topics/migrations/#workflow)' %
                               str(no_db))

        # populate db:
        self.printinfo('Populating DB with OpenQuake data:')
        errors = Error.objects  # noqa

        self.printinfo(' > Tectonic region types (Trt)')
        # Note: Contrarily to Imts and Gsims, for which we store "failing"
        # elements in a separate `errors` table above for debugging/inspection,
        # tectonic regions can not fail:
        trts = populate_trts()
        skipped = errors.filter(entity_type=DB_ENTITY.TRT.name).count()
        self.printsuccess('   %d written, %d skipped due to errors' %
                          (Trt.objects.count(), skipped))  # noqa

        self.printinfo(' > Intensity measure types (Imt)')
        imts = populate_imts()
        skipped = errors.filter(entity_type=DB_ENTITY.IMT.name).count()
        self.printsuccess('   %d written, %d skipped due to errors' %
                          (Imt.objects.count(), skipped))  # noqa

        self.printinfo(' > Ground shaking intensity models (Gsim)')
        populate_gsims(trts, imts)
        skipped = errors.filter(entity_type=DB_ENTITY.GSIM.name).count()
        self.printsuccess('   %d written, %d skipped due to errors' %
                          (Gsim.objects.count(), skipped))  # noqa

        # Scan the required Gsims attributes and their
        # mapping in the Flatfile (GmTable) columns, checking if some
        # attribute is not handled (this might happen in case OpenQuake
        # is upgraded and has some newly implemented Gsims):
        # In case of warnings, talk with G.W. and add the mappings in
        # GSIM_REQUIRED_ATTRS
        # TODO: this will be a Model to be implemented as abstract DB table
        gsim_names = Gsim.objects  # noqa
        gsim_names = gsim_names.values_list('key', flat=True)
        unknown_attrs = check_gsims_required_attrs(gsim_names)
        if unknown_attrs:
            self.printwarn(
                '\nWARNING: %d attributes are required for some Gsim in '
                'OpenQuake code, but do not have a mapping to any flatfile '
                'column and no default value provided.'
                '\nWithout that information, the program will still work '
                'but the Gsims might fail when computing their '
                '"measures of fit". To be safer, you should add those '
                'attributes to the variable egsim.core.utils.GSIM_REQUIRED_ATTRS' %
                len(unknown_attrs))
            self.printwarn('List of attributes:')
            for att, gsims in unknown_attrs.items():
                gsim_str = (str(_) for _ in gsims) if len(gsims) <= 2 else \
                    [str(gsims[0]), "other %d Gsims" % (len(gsims) - 1)]
                gsim_str = '(defined for "%s")' % (" and ".join(gsim_str))
                self.printwarn('%s %s' % (att, gsim_str))


def populate_trts() -> Dict[str, Trt]:
    """Writes all Tectonic region types from OpenQuake into the db,
        and returns the written instances"""
    trts = []
    # `create` below creates and saves an object
    # https://docs.djangoproject.com/en/3.1/ref/models/querysets/#django.db.models.query.QuerySet.create
    create_trt = Trt.objects.create  # noqa
    for attname in dir(TRT):
        if attname[:1] != '_' and isinstance(getattr(TRT, attname), str):
            # the key is set automatically from the oq_name (see models.py):
            try:
                trts.append(create_trt(oq_name=getattr(TRT, attname),
                                       oq_att=attname))
            except Exception as exc:
                # provide more meaningful message
                raise CommandError('Can not create db entry for TRT.%s: %s\n'
                                   '(check eGSIM code and the uniqueness of all '
                                   'attributes of openquake.hazardlib.const.TRT)' %
                                    (attname, str(exc)))

    return trts


def populate_imts() -> Dict[str, Imt]:
    """Writes all IMTs from OpenQuake to the db, skipping IMTs which need
    arguments as we do not know how to handle them (except SA)
    """
    # `create` below creates and saves an object
    # https://docs.djangoproject.com/en/3.1/ref/models/querysets/#django.db.models.query.QuerySet.create
    create_imt = Imt.objects.create  # noqa
    imts = []
    for imt_name, imt_class in hazardlib_imt_registry.items():
        if inspect.isabstract(imt_class):
            continue
        if imt_class != imt.SA:
            # test we did not need arguments if imt is not SA
            try:
                # this creates an instance of the class. If the instance
                # needs argument, it fails (except below)
                imt.from_string(imt_name)
            except Exception as exc:  # pylint: disable=broad-except
                create_error(DB_ENTITY.IMT, imt_name, exc)
                continue
        imts.append(create_imt(key=imt_name, needs_args=imt_class == imt.SA))
    return imts


def populate_gsims(trts, imts) -> Dict[str, Gsim]:
    """Writes all Gsims from OpenQuake to the db"""
    # entity_type = DB_ENTITY.GSIM
    trts_d = {_.oq_name: _ for _ in trts}
    imts_d = {_.key: _ for _ in imts}
    # `create` below creates and saves an object
    # https://docs.djangoproject.com/en/3.1/ref/models/querysets/#django.db.models.query.QuerySet.create
    create_gsim = Gsim.objects.create  # noqa
    gsims = []
    with warnings.catch_warnings():
        # Catch warnings as if they were exceptions, and skip deprecation w.
        # https://stackoverflow.com/a/30368735
        warnings.filterwarnings('error')  # raises every time, not only 1st
        for key, gsim in get_available_gsims().items():
            if inspect.isabstract(gsim):
                continue
            warning = ''
            needs_args = False

            try:
                gsim_inst = gsim()
            except OQDeprecationWarning as warn:
                # treat OpenQuake (OQ) deprecation warnings as errors. Note that
                # the builtin DeprecationWarning is silenced, OQ uses it's own
                create_error(DB_ENTITY.GSIM, key, exc)
                continue
            except Warning as warn:
                warning = str(warn)
            except TypeError:
                gsim_inst = gsim
                needs_args = True
            except (OSError, NotImplementedError, KeyError) as exc:
                # NOTE: ADD HERE THE EXCEPTIONS THAT YOU WANT TO JUST REPORT.
                create_error(DB_ENTITY.GSIM, key, exc)
                continue
            except Exception as _ex:
                # The most likely solution here is to add this exception to the
                # `except` clause above and skip the Gsim: raise but provide a
                # meaningful and more informative message to the user
                errmsg = ("Attempt to initialize %s raised %s which is "
                          "not handled in module %s (original err msg: %s)") % \
                         (str(gsim), _ex.__class__.__name__, __name__, str(_ex))
                raise Exception(errmsg) from _ex

            try:
                gsim_imts = gsim_inst.DEFINED_FOR_INTENSITY_MEASURE_TYPES
                # check #1:
                if not hasattr(gsim_imts, '__iter__'):
                    # gsim_imts is not iterable, raise (caught below):
                    raise TypeError('Associated IMT object not iterable')
                # check#2: first assure len(gsim_imts) works ...
                if not hasattr(gsim_imts, '__len__'):
                    gsim_imts = list(gsim_imts)
                # ... and that we have imts:
                if not len(gsim_imts):
                    raise TypeError('No IMT defined')  # caught here below

            except (AttributeError, TypeError) as exc:
                create_error(DB_ENTITY.GSIM, key, exc)
                continue

            try:
                trt = trts_d[gsim_inst.DEFINED_FOR_TECTONIC_REGION_TYPE]
            except Exception as exc:
                create_error(DB_ENTITY.GSIM, key,
                             "Invalid TRT: %s" % str(exc),
                             exc.__class__.__name__)
                continue

            # convert gsim imts (classes) into strings:
            gsim_imts = [_.__name__ for _ in gsim_imts]
            # and then convert to Imt model instances:
            gsim_imts = [imts_d[_] for _ in gsim_imts if _ in imts_d]
            if not gsim_imts:
                create_error(DB_ENTITY.GSIM, key, "No IMT found")
                continue

            gsim = create_gsim(key=key, trt=trt, warning=warning,
                               needs_args=needs_args)
            gsim.imts.set(gsim_imts)
            gsims.append(gsim)

    return gsims


def create_error(entity_type: DB_ENTITY,
                 entity_key: str,
                 error: Union[str, Exception],
                 error_type: str = None):
    """Creates an error from the given entity type (e.g. `DB_ENTITY.GSIM`) and
    key (e.g., the Gsim class name) and saves it to the database.
    Note: if error_type is missing or None it is set as:
        `error.__class__.__name__` if `error` is an `Exception`
        "Error" otherwise
    """
    assert isinstance(entity_type, DB_ENTITY)
    if not error_type:
        error_type = error.__class__.__name__ \
            if isinstance(error, Exception) else 'Error'

    Error.objects.create(type=error_type.name,  # <- enum name (e.g. "GSIM")
                         message=str(error),
                         entity_type=entity_type,
                         entity_key=entity_key)


def check_gsims_required_attrs(gsim_names):
    """Checks that the attributes handled in GSIM_REQUIRED_ATTRS cover all
    OpenQuake required attributes implemented for all gsims

    :param gsim_names: iterable of strings denoting the Gsims in the database
    """
    unknowns = defaultdict(list)
    for gsim in gsim_names:
        attrs = OQ.required_attrs(gsim)
        for att in attrs:
            if att not in get_gsim_required_attrs_dict():
                unknowns[att].append(gsim)
    return unknowns


def get_gsim_required_attrs_dict():
    """wrapper returning `GSIM_REQUIRED_ATTRS`, useful for unit-testing"""
    return GSIM_REQUIRED_ATTRS
