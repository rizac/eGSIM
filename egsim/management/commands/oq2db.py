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

from django.db.utils import OperationalError
from django.core.management.base import BaseCommand, CommandError
from openquake.baselib.general import (DeprecationWarning as
                                       OQDeprecationWarning)
from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib.imt import registry as hazardlib_imt_registry, IMT
from openquake.hazardlib.const import TRT
from openquake.hazardlib import imt

from egsim.management.commands._utils import EgsimBaseCommand
from egsim.models import Gsim, Imt, Trt, Error, ENTITIES, empty_all
from egsim.core.utils import OQ, GSIM_REQUIRED_ATTRS


class Command(EgsimBaseCommand):
    """Command to initialize the db: python manage.py oq2db
    """
    help = ('Initializes and populates eGSIM database with OpenQuake data '
            '(e.g., Gsim, Imt, Trt)')

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
        trts = populate_trts()
        skipped = errors.filter(entity_type=ENTITIES[2][0]).count()
        self.printsuccess('   %d written, %d skipped due to errors' %
                          (Trt.objects.count(), skipped))  # noqa

        self.printinfo(' > Intensity measure types (Imt)')
        imts = populate_imts()
        skipped = errors.filter(entity_type=ENTITIES[1][0]).count()
        self.printsuccess('   %d written, %d skipped due to errors' %
                          (Imt.objects.count(), skipped))  # noqa

        self.printinfo(' > Ground shaking intensity models (Gsim)')
        populate_gsims(trts, imts)
        skipped = errors.filter(entity_type=ENTITIES[0][0]).count()
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


def populate_trts():
    """Writes all Tectonic region types from OpenQuake into the db,
        and returns the written instances"""
    trts = []
    create_trt = Trt.objects.create  # noqa
    for attname in dir(TRT):
        if attname[:1] != '_' and isinstance(getattr(TRT, attname), str):
            # the key is set automatically from the oq_name (see models.py):
            trts.append(create_trt(oq_name=getattr(TRT, attname),
                                   oq_att=attname))
    return trts


def populate_imts():
    """Writes all IMTs from OpenQuake to the db, skipping IMTs which need
    arguments as we do not know how to handle them (except SA)
    """
    entity_type = ENTITIES[1][0]
    create_err = Error.objects.create  # noqa
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
                create_err(type=exc.__class__.__name__,
                           message=str(exc),
                           entity_type=entity_type,
                           entity_key=imt_name)
                continue
        imts.append(create_imt(key=imt_name, needs_args=imt_class == imt.SA))
    return imts


def populate_gsims(trts, imts):
    """Writes all Gsims from OpenQuake to the db"""
    entity_type = ENTITIES[0][0]
    trts_d = {_.oq_name: _ for _ in trts}
    imts_d = {_.key: _ for _ in imts}
    create_err = Error.objects.create  # noqa
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
                create_err(type=warn.__class__.__name__,
                           message=str(warn),
                           entity_type=entity_type,
                           entity_key=key)
                continue
            except Warning as warn:
                warning = str(warn)
            except TypeError:
                gsim_inst = gsim
                needs_args = True
            except (OSError, NotImplementedError, KeyError) as exc:
                # NOTE: LIST OF EXCEPTIONS SKIPPING THE CORRESPONDING Gsim
                create_err(type=exc.__class__.__name__,
                           message=str(exc),
                           entity_type=entity_type,
                           entity_key=key)
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
                create_err(type=exc.__class__.__name__,
                           message=str(exc),
                           entity_type=entity_type,
                           entity_key=key)
                continue

            try:
                trt = trts_d[gsim_inst.DEFINED_FOR_TECTONIC_REGION_TYPE]
            except KeyError:
                create_err(type=Exception.__name__,
                           message='%s is not a valid TRT' %
                           str(gsim_inst.DEFINED_FOR_TECTONIC_REGION_TYPE),
                           entity_type=entity_type,
                           entity_key=key)
                continue
            except AttributeError:
                create_err(type=Exception.__name__,
                           message='No TRT defined',
                           entity_type=entity_type,
                           entity_key=key)
                continue

            # convert gsim imts (classes) into strings:
            gsim_imts = [_.__name__ for _ in gsim_imts]
            # and then convert to Imt model instances:
            gsim_imts = [imts_d[_] for _ in gsim_imts if _ in imts_d]
            if not gsim_imts:
                create_err(type=Exception.__name__,
                           message='No IMT in %s' % str([_.key for _ in imts]),
                           entity_type=entity_type,
                           entity_key=key)
                continue
            gsim = create_gsim(key=key, trt=trt, warning=warning,
                               needs_args=needs_args)
            gsim.imts.set(gsim_imts)
            gsims.append(gsim)

    return gsims


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
