'''
Module for initalizing the databse with OpenQuake information
and custom tectonic regions

For info see:
https://django.readthedocs.io/en/2.0.x/howto/custom-management-commands.html

Created on 6 Apr 2019

@author: riccardo
'''
import os
import warnings
import inspect
from collections import defaultdict

from django.db.utils import OperationalError
from django.core.management.base import BaseCommand, CommandError
from openquake.baselib.general import (DeprecationWarning as
                                       OQDeprecationWarning)
from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib.imt import registry as hazardlib_imt_registry
from openquake.hazardlib.const import TRT
from openquake.hazardlib import imt


from egsim.models import Gsim, Imt, Trt, Error, TectonicRegion, ENTITIES, \
    empty_all
from egsim.core.utils import OQ, GSIM_REQUIRED_ATTRS
from ._tectonic_regionalisations import share

# these are the functions to populate the TectonicRegion model.
# For info on implementing new ones, see _tectonic_regionalisations/README.txt
# The key is the model name, the value is the relative function
TECREG_FUNCTIONS = {'SHARE': share.create}


class Command(BaseCommand):
    '''Command to initialize the db:
        python manage.py initdb
    '''
    help = ('Initializes and  populates the database with all GSIMs, IMTs and '
            'TRTs (Tectonic region types) of OpenQuake. Additionally, if any '
            'tectonic regionalisation is implemented, (see '
            '\'commands/_tectonic_regionalisations/README.txt\''
            ' for details) adds it to the database '
            '(a tectonic regionalisation is a set of Geographic ploygons each '
            'with a specific TRT assigned)')

#     def add_arguments(self, parser):
#         parser.add_argument('poll_id', nargs='+', type=int)

    def handle(self, *args, **options):
        # some shorthands for printing
        def printinfo(msg):
            self.stdout.write(msg)

        def printerr(msg):
            self.stdout.write(self.style.ERROR(msg))

        def printok(msg):
            self.stdout.write(self.style.SUCCESS(msg))

        # (for info on CommandError below, it is an Exception just handled by
        # Django to print nicely the error on the terminal)

        # delete db:
        try:
            printinfo('Emptying DB Tables')
            empty_all()
        except OperationalError as no_db:
            raise CommandError('%s.\nDid you create the db first?\n(for '
                               'info see: https://docs.djangoproject.'
                               'com/en/2.2/topics/migrations/#workflow)' %
                               str(no_db))

        # populate db:
        printinfo('Populating DB with OpenQuake data:')

        printinfo(' Tectonic region types (Trt)')
        trts = populate_trts()

        printinfo(' Intensity measure types (Imt)')
        imts = populate_imts()

        printinfo(' Ground shaking intensity models (Gsim)')
        populate_gsims(trts, imts)

        printinfo('Writing Tectonic regions (Tr) from provided Tr models')
        printinfo('Found %d model(s): %s' %
                  (len(TECREG_FUNCTIONS),
                   list(TECREG_FUNCTIONS.keys())))
        for model, func in TECREG_FUNCTIONS.items():
            tecregions = func(trts)
            for trg in tecregions:
                trg.model = model
                trg.save()

        # summary:
        trts = Trt.objects.count()  # pylint: disable=no-member
        imts = Imt.objects.count()  # pylint: disable=no-member
        gsims = Gsim.objects.count()  # pylint: disable=no-member

        errors = Error.objects  # pylint: disable=no-member
        g_errs = errors.filter(entity_type=ENTITIES[0][0]).count()
        i_errs = errors.filter(entity_type=ENTITIES[1][0]).count()
        t_errs = errors.filter(entity_type=ENTITIES[2][0]).count()

        printok('\nSuccessfully populated the db:')
        printok('OpenQuake data written:')
        printok('  %d Trt(s) (%d skipped due to errors)' % (trts, t_errs))
        printok('  %d Imt(s) (%d skipped due to errors)' % (imts, i_errs))
        printok('  %d Gsim(s) (%d skipped due to errors)' % (gsims, g_errs))
        trs = TectonicRegion.objects  # pylint: disable=no-member
        for key in TECREG_FUNCTIONS:
            printok('%d Tectonic region(s) written (model: %s)' %
                    (trs.filter(model=key).count(), key))

        # Scan the required Gsims attributes and their
        # mapping in the Flatfile (GmTable) columns, checking if some
        # attribute is not handled (this might happen in case OpenQuake
        # is upgraded and has some newly implemented Gsims):
        # In case of warnings, talk with G.W. and add the mappings in
        # GSIM_REQUIRED_ATTRS
        # FIXME: this will be a Model to be implemented as abstract DB table
        gsim_names = Gsim.objects  # pylint: disable=no-member
        gsim_names = gsim_names.values_list('key', flat=True)
        unknown_attrs = check_gsims_required_attrs(gsim_names)
        if unknown_attrs:
            printerr('\nWARNING: %d attributes are defined as required '
                     'for some OpenQuake Gsims, but are not handled in '
                     'egsim.core.utils.GSIM_REQUIRED_ATTRS. '
                     'This is not critical but might result in faling '
                     '"measures of fit" computations due to NaNs' %
                     len(unknown_attrs))
            printerr('List of attributes:')
            for att, gsims in unknown_attrs.items():
                gsim_str = '(defined for "%s"' % str(gsims[0])
                if len(gsims) > 1:
                    gsim_str += ' and other %d Gsims)' % (len(gsims)-1)
                else:
                    gsim_str += ')'
                printerr('%s %s' % (att, gsim_str))


def populate_trts():
    '''Writes all Tectonic region types from OpenQuake into the db,
        and returns the written instances'''
    trts = []
    create_trt = Trt.objects.create  # pylint: disable=no-member
    for attname in dir(TRT):
        if attname[:1] != '_' and isinstance(getattr(TRT, attname), str):
            # the key is set automatically from the oq_name (see models.py):
            trts.append(create_trt(oq_name=getattr(TRT, attname),
                                   oq_att=attname))
    return trts


def populate_imts():
    '''Writes all IMTs from OpenQuake to the db, skipping IMTs which need
    arguments as we do not know how to handle them (except SA)
    and I know that (asd iuasd) for a moment ( an
    d no other way) ()   () ()
    (
     ())()()
    '''
    entity_type = ENTITIES[1][0]
    create_err = Error.objects.create  # pylint: disable=no-member
    create_imt = Imt.objects.create  # pylint: disable=no-member
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
    '''Writes all Gsims from OpenQuake to the db'''
    entity_type = ENTITIES[0][0]
    trts_d = {_.oq_name: _ for _ in trts}
    imts_d = {_.key: _ for _ in imts}
    create_err = Error.objects.create  # pylint: disable=no-member
    create_gsim = Gsim.objects.create  # pylint: disable=no-member
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
            except TypeError:
                gsim_inst = gsim
                needs_args = True
            except (OSError, NotImplementedError) as exc:
                create_err(type=exc.__class__.__name__,
                           message=str(exc),
                           entity_type=entity_type,
                           entity_key=key)
                continue
            except OQDeprecationWarning as warn:
                # the builtin DeprecationWarning is silenced, OQ uses it's own
                create_err(type=warn.__class__.__name__,
                           message=str(warn),
                           entity_type=entity_type,
                           entity_key=key)
                continue
#             except NotVerifiedWarning as warn:
#                 warning = str(warn)
            except Warning as warn:
                warning = str(warn)
            except Exception as general_exc:
                # some general exception (Openquake 3.10 raises a KeyError for instance)
                create_err(type=general_exc.__class__.__name__,
                           message=str(general_exc),
                           entity_type=entity_type,
                           entity_key=key)
                continue

            try:
                gsim_imts = gsim_inst.DEFINED_FOR_INTENSITY_MEASURE_TYPES
            except AttributeError as exc:
                create_err(type=exc.__class__.__name__,
                           message=str(exc),
                           entity_type=entity_type,
                           entity_key=key)
                continue

            if not gsim_imts and hasattr(gsim_imts, '__iter__'):
                create_err(type=Exception.__name__,
                           message='No IMT defined',
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
            # and not convert to Imt model instances:
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
    '''Checks that the attributes handled in GSIM_REQUIRED_ATTRS cover all
    OpenQuake required attributes implemented for all gsims

    :param gsim_names: iterable of strings denoting the Gsims in the database
    '''
    unknowns = defaultdict(list)
    for gsim in gsim_names:
        attrs = OQ.required_attrs(gsim)
        for att in attrs:
            if att not in get_gsim_required_attrs_dict():
                unknowns[att].append(gsim)
    return unknowns


def get_gsim_required_attrs_dict():
    '''wrapper returning `GSIM_REQUIRED_ATTRS`, useful for unit-testing'''
    return GSIM_REQUIRED_ATTRS
