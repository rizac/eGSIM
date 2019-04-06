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
from collections import OrderedDict
from importlib import import_module

from openquake.baselib.general import DeprecationWarning as OQDeprecationWarning
from openquake.hazardlib.gsim.base import NotVerifiedWarning
from openquake.hazardlib.gsim import get_available_gsims
from openquake.hazardlib.imt import registry as hazardlib_imt_registry
from openquake.hazardlib.const import TRT
from openquake.hazardlib import imt
from django.core.management.base import BaseCommand, CommandError

from egsim.models import Gsim, Imt, Trt, Error, TectonicRegion, ENTITIES, \
    empty_all
from django.db.utils import OperationalError



class Command(BaseCommand):
    help = ('Initializes the database and creates with OpenQuake information'
            'and tectonic regions. The latter can be incremented by writing'
            'a new folder in the `egsim/management/commands/tr_models`'
            'directory, and putting shape files (.shp) therein')

#     def add_arguments(self, parser):
#         parser.add_argument('poll_id', nargs='+', type=int)

    def handle(self, *args, **options):

        # delete db:
        self.stdout.write('Emptying DB Tables')
        try:
            try:
                empty_all()
            except OperationalError as no_db:
                raise CommandError('%s.\nDid you create the db first?\n(for '
                                   'info see: https://docs.djangoproject.'
                                   'com/en/2.2/topics/migrations/#workflow)' %
                                   str(no_db))

            # set data        
            self.stdout.write('Writing OQ data (Trt, IMT, GSIMs)')
            trts, imts = get_trts(), get_imts()
            get_gsims(trts, imts)

            tecregions = import_trs_functions()
            self.stdout.write('Writing Tectonic regions from provided models')
            self.stdout.write('Found %d model(s): %s' % (len(tecregions),
                                                         list(tecregions.keys())))

            for model, func in tecregions:
                tecregions = func(trts)
                for t in tecregions:
                    t.model = model
                    t.save()

            self.stdout.write(self.style.SUCCESS('Successfully initialized the db'))
        except CommandError:
            raise
        except Exception as exc:
            raise CommandError(exc)
   

def get_trts():
    '''Writes all Tectonic region types from OpenQuake into the db,
        and returns the written instances'''
    trts = []
    create_trt = Trt.objects.create  # pylint: disable=no-member
    for attname in dir(TRT):
        if attname[:1] != '_' and isinstance(getattr(TRT, attname), str):
            trts.append(create_trt(key=getattr(TRT, attname).
                                   replace(' ', '_').lower(),
                                   oq_name=getattr(TRT, attname),
                                   oq_att=attname))
    return trts


def get_imts():
    '''Writes all IMTs from OpenQuake to the db, skipping IMTs which need
    arguments as we do not know how to handle them (except SA)'''
    entyty_type = ENTITIES[1][0]
    create_err = Error.objects.create  # pylint: disable=no-member
    create_imt = Imt.objects.create  # pylint: disable=no-member
    imts = []
    for imt_name, imt_class in hazardlib_imt_registry.items():
        if imt_class != imt.SA:  # test we di not need arguments if imt is not SA
            try:
                # this creates an instance of the class. If the instance needs argument,
                # it fails (except below)
                imt.from_string(imt_name)
            except Exception as exc:  # pylint: disable=broad-except
                create_err(type=exc.__class__.__name__,
                           message=str(exc),
                           entyty_type=entyty_type,
                           entity_name=imt_name)
                continue
            imts.append(create_imt(key=imt_name, needs_args=imt_class==imt.SA))
    return imts


def get_gsims(trts, imts):
    entyty_type = ENTITIES[0][0]
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
                           entyty_type=entyty_type,
                           entity_name=key)
                continue
            except OQDeprecationWarning as warn:
                # the builtin DeprecationWarning is silenced, OQ uses it's own
                create_err(type=warn.__class__.__name__,
                           message=str(warn),
                           entyty_type=entyty_type,
                           entity_name=key)
                continue
#             except NotVerifiedWarning as warn:
#                 warning = str(warn)
            except Warning as warn:
                warning = str(warn)
            try:
                gsim_imts = gsim_inst.DEFINED_FOR_INTENSITY_MEASURE_TYPES
            except AttributeError as exc:
                create_err(type=exc.__class__.__name__,
                           message=str(exc),
                           entyty_type=entyty_type,
                           entity_name=key)
                continue
            if not gsim_imts and hasattr(gsim_imts, '__iter__'):
                create_err(type=Exception.__name__,
                           message='No IMT defined',
                           entyty_type=entyty_type,
                           entity_name=key)
                continue
            try:
                trt = trts_d[gsim_inst.DEFINED_FOR_TECTONIC_REGION_TYPE]
            except KeyError:
                create_err(type=Exception.__name__,
                           message='%s is not a valid TRT' %
                           str(gsim_inst.DEFINED_FOR_TECTONIC_REGION_TYPE),
                           entyty_type=entyty_type,
                           entity_name=key)
                continue
            except AttributeError:
                create_err(type=Exception.__name__,
                           message='No TRT defined',
                           entyty_type=entyty_type,
                           entity_name=key)
                continue
            gimts = [imts_d[_] for _ in gsim_imts if _ in imts_d]
            if not gimts:
                create_err(type=Exception.__name__,
                           message='No IMT in %s' % str([_.key for _ in imts]),
                           entyty_type=entyty_type,
                           entity_name=key)
                continue
            gsim = create_gsim(key=key, trt=trt, warning=warning,
                               needs_args=needs_args)
            gsim.set(gimts)
            gsims.append(gsim)

    return gsims


def import_trs_functions():
    root = os.path.join(os.path.dirname(__file__),
                        'tectonic_regionalisations')
    ret = {}
    for model in os.listdir(root):        
        mod = import_module(os.path.join(root, model))
        met = getattr(mod, 'create')
        if hasattr(met, '__call__'):
            ret[model] = met

    return ret
    


