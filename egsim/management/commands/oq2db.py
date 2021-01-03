"""
Command to initialize and populate the eGSIM database with all GSIMs, IMTs
(and their relations) implemented in the currently used version of OpenQuake

Created on 6 Apr 2019

@author: riccardo
"""
import json
import os
import re
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

from egsim.management.commands._utils import EgsimBaseCommand, get_command_datadir
from egsim.management.commands import emptydb
from egsim.models import Gsim, Imt, Trt, Error, EntityType
from egsim.core.utils import OQ, GSIM_REQUIRED_ATTRS, yaml_load


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
        # delete db:
        emptydb.Command().handle()
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
        skipped = errors.filter(entity_type=EntityType.TRT).count()
        self.printsuccess('   %d written, %d skipped due to errors' %
                          (Trt.objects.count(), skipped))  # noqa

        self.printinfo(' > Intensity measure types (Imt)')
        imts = populate_imts()
        skipped = errors.filter(entity_type=EntityType.IMT).count()
        self.printsuccess('   %d written, %d skipped due to errors' %
                          (Imt.objects.count(), skipped))  # noqa

        self.printinfo(' > Ground shaking intensity models (Gsim)')
        populate_gsims(trts, imts)
        skipped = errors.filter(entity_type=EntityType.GSIM).count()
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
    """Write all Tectonic region types found in the associated YAML file
    and returns a dict of names mapped to the associated Trt (many to one
    relationship: the same Trt might be keyed by many names)
    """
    def normalize(string):
        """normalize two trt strings for comparison"""
        return re.sub(r'\s+', ' ', string.strip().lower())

    # get all OQ TRTs, by name:
    oq_trts = {n: normalize(v) for n, v in OQ.trts().items()}
    # define the keys as the attribute values (lower case and no underscore)
    egsim_trt_file = os.path.join(get_command_datadir(__name__), 'trt.yaml')
    egsim_trts = yaml_load(egsim_trt_file)
    if not all(re.match('^[a-z_]+$', _) for _ in egsim_trts):
        raise CommandError('Trt key(s) invalid (allowed lower case a to z, or '
                           'underscore)')
    # No duplicated name in `egsim_trts`:
    already_processed_names = set()
    # all OpenQuake TRT must have a match in `egsim_trts`:
    oq_attname_unmatched = set(oq_trts.keys())
    trts = []
    for key, values in egsim_trts:
        # create the Trt object. The names attribute is basically the `values`
        # variable space-separated, using json.dumps to escape quotes in case
        trt = Trt(key=key, aliases_jsonlist=json.dumps(values), oq_attname=None)
        trts.append(trt)
        values = set(normalize(_) for _ in values)
        # check uniqueness of names:
        for _ in values:
            if _ in already_processed_names:
                raise CommandError('Trt "%s" not unique in "%s" (after '
                                   'normalization)' % (_, egsim_trt_file))
            already_processed_names.add(_)

        # find associated OpenQuake TRT (if any):
        for oq_attname in oq_attname_unmatched:
            oq_attvalue = oq_trts[oq_attname]
            if oq_attvalue in values:
                trt.oq_attname = oq_attname
                oq_attname_unmatched.remove(oq_attname)
                break

    if oq_attname_unmatched:
        names = ', '.join(sorted(oq_trts[_] for _ in oq_attname_unmatched))
        raise CommandError('No match found for the following OpenQuake '
                           'TRT(s): %s.\n'
                           'Please add them in "%s"' %
                           (names, egsim_trt_file))

    ret_trts = {}  # Trt name (str) -> Trt (Trt object). It's a many to one relationship
    # `create` below creates and saves an object
    # https://docs.djangoproject.com/en/3.1/ref/models/querysets/#django.db.models.query.QuerySet.create
    create_trt = Trt.objects.create  # noqa
    for trt in trts:
        try:
            trt.save()
            for name in egsim_trts[trt.key]:  # Trt names as in the YAML
                ret_trts[name] = Trt
        except Exception as exc:
            # provide more meaningful message
            raise CommandError('Can not create db entry for TRT "%s": %s\n'
                               '(check file "%s" and eGSIM code)' %
                               (trt, egsim_trt_file))

    return ret_trts


def populate_imts() -> Dict[str, Imt]:
    """Write all IMTs from OpenQuake to the db, skipping IMTs which need
    arguments as we do not know how to handle them (except SA)
    """
    # `create` below creates and saves an object
    # https://docs.djangoproject.com/en/3.1/ref/models/querysets/#django.db.models.query.QuerySet.create
    create_imt = Imt.objects.create  # noqa
    imts = {}
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
                create_error(EntityType.IMT, imt_name, exc)
                continue
        imts[imt_name] = create_imt(key=imt_name, needs_args=imt_class == imt.SA)
    return imts


def populate_gsims(trts: Dict[str, Trt], imts: Dict[str, Imt]) -> Dict[str, Gsim]:
    """Write all Gsims from OpenQuake to the db"""
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
            gsim_warnings = []
            needs_args = False

            try:
                gsim_inst = gsim()
            except OQDeprecationWarning as warn:
                # treat OpenQuake (OQ) deprecation warnings as errors. Note that
                # the builtin DeprecationWarning is silenced, OQ uses it's own
                create_error(EntityType.GSIM, key, exc)
                continue
            except Warning as warn:
                gsim_warnings.append(str(warn))
            except TypeError:
                gsim_inst = gsim
                needs_args = True
            except (OSError, NotImplementedError, KeyError) as exc:
                # NOTE: ADD HERE THE EXCEPTIONS THAT YOU WANT TO JUST REPORT.
                create_error(EntityType.GSIM, key, exc)
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
                create_error(EntityType.GSIM, key, exc)
                continue

            trt = None
            try:
                defined_trt = str(gsim_inst.DEFINED_FOR_TECTONIC_REGION_TYPE)
                trt = trts[defined_trt]
            except AttributeError:
                gsim_warnings.append('No Trt defined')
            except KeyError:
                gsim_warnings.append('Trt "%s" invalid' % defined_trt)

            # convert gsim imts (classes) into strings:
            gsim_imts = [_.__name__ for _ in gsim_imts]
            # and then convert to Imt model instances:
            gsim_imts = [imts[_] for _ in gsim_imts if _ in imts]
            if not gsim_imts:
                create_error(EntityType.GSIM, key, "No IMT found")
                continue

            # pack the N>=0 warning messages into a single msg.
            # If N > 1, prepend each msg with  "1) ...", "2) ...", ...
            gsim_warning = ''
            if len(gsim_warnings) == 1:
                gsim_warning = gsim_warnings[0].strip()
            elif len(gsim_warnings) > 1:
                gsim_warning = " ".join('%d) %s' % (i, _.strip())
                                        for (i, _) in enumerate(gsim_warnings, 1))

            gsim = create_gsim(key=key, trt=trt, warning=gsim_warning or None,
                               needs_args=needs_args)
            gsim.imts.set(gsim_imts)
            gsims.append(gsim)

    return gsims


def create_error(entity_type: EntityType,
                 entity_key: str,
                 error: Union[str, Exception],
                 error_type: str = None):
    """Creates an error from the given entity type (e.g. `DB_ENTITY.GSIM`) and
    key (e.g., the Gsim class name) and saves it to the database.
    Note: if `error_type` is missing or None it is set as:
        1. `error.__class__.__name__` if `error` is an `Exception`
        2. "Error" otherwise
    """
    assert isinstance(entity_type, EntityType)
    if not error_type:
        error_type = error.__class__.__name__ \
            if isinstance(error, Exception) else 'Error'

    Error.objects.create(type=error_type,
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
