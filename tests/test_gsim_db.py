'''
Created on 5 Apr 2019

@author: riccardo
'''
from itertools import product

import pytest

from egsim.models import Gsim, Trt, Imt
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q


@pytest.mark.django_db
def test_db_0(django_db_setup):
    with pytest.raises(ObjectDoesNotExist):  # @UndefinedVariable
        me = Gsim.objects.get()  # pylint: disable=no-member

    # FIXME: how to query objects?
    # FIXME: see help_text!!!!

    # ANyway, populate db:
    trt1 = Trt.objects.\
        create(key='active_shallow_crust')  # pylint: disable=no-member
    trt2 = Trt.objects.\
        create(key='stable_shallow_crust')  # pylint: disable=no-member

    imt1 = Imt.objects.create(key='PGA')  # pylint: disable=no-member
    imt2 = Imt.objects.\
        create(key='SA', needs_args=True)  # pylint: disable=no-member

    gsims = []
    for imt, trt, warn in product([imt1, imt2], [trt1, trt2],
                                  [None, 'warning']):
        gsim = Gsim.objects.create(key=str(len(gsims)+1), warning=warn,
                                   trt=trt)
        if warn:
            gsim.imts.set([imt1, imt2])
        elif imt is imt1:
            gsim.imts.set([imt1])

        gsims.append(gsim)

    # there are:
    # 4 gsims with trt1
    # 4 gsims with trt2
    # 4 gsims with imt1 and imt2
    # 2 gsims with imt1
    # 2 gims with no imt

    test1 = [_ for _ in get_gsims()]
    assert len(test1) == len(gsims)

    # Note that below we can supply each instance key (string, e.g.
    # 'PGA') or the entity itself. Same for trt

    test1 = [_ for _ in get_gsims(imts=['PGA', 'SA'])]
    assert len(test1) == 6

    test1 = [_ for _ in get_gsims(trts=[trt1.key], imts=[imt1.key])]
    assert len(test1) == 3

    test1 = [_ for _ in get_gsims(trts=[trt2.key], imts=[imt1.key])]
    assert len(test1) == 3

    test1 = [_ for _ in get_gsims(trts=[trt1.key], imts=[imt2.key])]
    assert len(test1) == 2

    test1 = [_ for _ in get_gsims(trts=[trt2.key], imts=[imt2.key])]
    assert len(test1) == 2

    test1 = get_gsims(imts=[imt1, imt2])
    assert len(test1) == 6

    test1 = [_ for _ in get_gsims(imts=[imt1])]
    assert len(test1) == 6

    test1 = [_ for _ in get_gsims(imts=[imt2])]
    assert len(test1) == 4

    test1 = [_ for _ in get_gsims(trts=[trt1])]
    assert len(test1) == 4

    test1 = [_ for _ in get_gsims(trts=[trt1.key])]
    assert len(test1) == 4

    # select_related does not seem to add duplicates:
    sel1 = _get_gsims(select_related=False).all()
    sel2 = _get_gsims(select_related=True).all()
    assert len(sel1) == len(sel2)
    
    alljson = db_asjson()
    assert len(alljson) == 8
    assert [_[0] for _ in alljson] == sorted(_.key for _ in gsims)


def db_asjson(sort=True):
    '''
        Returns a tuple of Gsims in json serializable format:
        (gsim.key, [gsim.imt1.key, .. gsim.imtN.key], gsim.trt, gsim.warning)
        where all tuple elements are strings.

        :param sort: returns the Gsim sorted according to their key (Gsim
            unique name)
    '''
    ret = {}  # in python 3.7+ dicts preserve insertion order
    query = _get_gsims(select_related=True)
    if sort:
        query = query.order_by('key')
    for gsim in query.all():
        if gsim.key in ret:  # should not happen, but for safety
            continue
        ret[gsim.key] = gsim.asjson()
    return tuple(ret.values())


def get_gsims(imts=None, trts=None, sort=True):
    '''
        Returns a QuerySet (list-like object) of Gsim instances matching the
        given criteria (i.e., matching the given imts AND trts)

        :param imts: iterable of strings (Imt.key) or Imt instances, or both.
            If None (the default), no filter is applied. Otherwise, return
            Gsims having any of the provided imt(s) (logical OR)
        :param trts: iterable of strings (Trt.key) or Trt instances, or both.
            If None (the default), no filter is applied. Otherwise, return
            only Gsims defined for any of the provided trt(s)  (logical OR)
        :param sort: returns the Gsim sorted according to their key (Gsim
            unique name)
    '''
    ret = _get_gsims(imts, trts, False).distinct()
    if sort:
        ret = ret.order_by('key')
    return ret.all()


def _get_gsims(imts=None, trts=None, select_related=False):
    '''
        Returns a Manager of Gsim instances matching the given
        criteria (i.e., matching the given imts AND trts)
        
        :param imts: iterable of strings (Imt.key) or Imt instances, or both.
            If None (the default), no filter is applied. Otherwise, return
            Gsims having any of the provided imt(s) (logical OR)
        :param trts: iterable of strings (Trt.key) or Trt instances, or both.
            If None (the default), no filter is applied. Otherwise, return
            only Gsims defined for any of the provided trt(s)  (logical OR)
        :param select_related: boolean (default: False). Selects also related
            Object so that they will be accessible without further database
            queries (which might speed up the process), so that, e.g.
            gsim.imts.all() will not query the db.
    '''
    # trt can be a trt instance, an int denoting the trt pkey,
    # or a string denoting the trt key field (unique)
    # in the expressions .filter(imts_in=[...]) the arguments in
    # list can be pkey (ints) or instances. We want to allow also
    # to pass imt keys (names). In this case we need to use
    # the Q function. For info see:
    # https://docs.djangoproject.com/en/2.2/topics/db/examples/many_to_one/
    # https://docs.djangoproject.com/en/2.2/topics/db/queries/
    
    gsims = Gsim.objects
    if select_related:
        gsims = gsims.prefetch_related('imts').select_related('trt')

    if imts is not None:
        if not any(isinstance(_, str) for _ in imts):
            gsims = gsims.filter(imts__in=imts)
        else:
            expr = None
            for _ in imts:
                if isinstance(_, str):
                    expr_chunk = Q(imts__key=_)
                else:
                    expr_chunk = Q(imts=_)
                if expr is None:
                    expr = expr_chunk
                else:
                    expr |= expr_chunk
            gsims = gsims.filter(expr)

    if trts is not None:
        if not any(isinstance(_, str) for _ in trts):
            gsims = gsims.filter(trt__in=trts)
        else:
            expr = None
            for _ in trts:
                if isinstance(_, str):
                    expr_chunk = Q(trt__key=_)
                else:
                    expr_chunk = Q(trt=_)
                if expr is None:
                    expr = expr_chunk
                else:
                    expr |= expr_chunk
            gsims = gsims.filter(expr)

    return gsims
