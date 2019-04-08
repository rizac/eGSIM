'''
Created on 5 Apr 2019

@author: riccardo
'''
from itertools import product
import uuid

import pytest
from django.core.exceptions import ObjectDoesNotExist

from egsim.models import Gsim, Trt, Imt, gsim_names, aval_gsims, \
    aval_imts, aval_trts, aval_trmodels, TectonicRegion


@pytest.mark.django_db
def test_db_0(django_db_setup):
    '''Tests the egsim db'''
    with pytest.raises(ObjectDoesNotExist):  # @UndefinedVariable
        Gsim.objects.get()  # pylint: disable=no-member

    # ANyway, populate db:
    trtcreate = Trt.objects.create  # pylint: disable=no-member
    trt1 = trtcreate(oq_name='active_shallow_crust', oq_att='asc')
    trt2 = trtcreate(oq_name='stable_shallow_crust', oq_att='ssc')

    imtcreate = Imt.objects.create  # pylint: disable=no-member
    imt1 = imtcreate(key='PGA')
    imt2 = imtcreate(key='SA', needs_args=True)

    gsims = []
    gsimcreate = Gsim.objects.create  # pylint: disable=no-member
    for imt, trt, warn in product([imt1, imt2], [trt1, trt2],
                                  [None, 'warning']):
        # generate a random string. This also implies almost certainly to
        # insert gsims non alphabetically
        key = str(uuid.uuid4())
        gsim = gsimcreate(key=key, warning=warn, trt=trt)
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

    test1 = list(gsim_names())
    assert len(test1) == len(gsims)

    # Note that below we can supply each instance key (string, e.g.
    # 'PGA') or the entity itself. Same for trt

    test1 = list(gsim_names(imts=['PGA', 'SA']))
    assert len(test1) == 6

    test1 = list(gsim_names(trts=[trt1.key], imts=[imt1.key]))
    assert len(test1) == 3

    test1 = list(gsim_names(trts=[trt2.key], imts=[imt1.key]))
    assert len(test1) == 3

    test1 = list(gsim_names(trts=[trt1.key], imts=[imt2.key]))
    assert len(test1) == 2

    test1 = list(gsim_names(trts=[trt2.key], imts=[imt2.key]))
    assert len(test1) == 2

    test1 = list(gsim_names(imts=[imt1, imt2]))
    assert len(test1) == 6

    test1 = list(gsim_names(imts=[imt1]))
    assert len(test1) == 6

    test1 = list(gsim_names(imts=[imt2]))
    assert len(test1) == 4

    test1 = list(gsim_names(trts=[trt1]))
    assert len(test1) == 4

    test1 = list(gsim_names(trts=[trt1.key]))
    assert len(test1) == 4

    # select_related does not seem to add duplicates:
    test1_ = list(gsim_names(gsims=[gsims[0].key]))
    test2_ = list(gsim_names(gsims=[gsims[0]]))
    test3_ = list(gsim_names(gsims=[gsims[0].id]))
    assert test1_ == test2_ == test3_

    test1_ = list(gsim_names(gsims=[gsims[0].key, gsims[1]]))
    test2_ = list(gsim_names(gsims=[gsims[0], gsims[1].id]))
    test3_ = list(gsim_names(gsims=[gsims[0].id, gsims[1].key]))
    assert test1_ == test2_ == test3_

    alljson = list(aval_gsims(asjsonlist=True))
    assert len(alljson) == 8
    assert [_[0] for _ in alljson] == sorted(_.key for _ in gsims)

    # test aval_imts and aval_gsims
    gsims_ = aval_gsims()
    imts_ = aval_imts()
    trts_ = aval_trts()
    assert list(gsims_) == sorted(_.key for _ in gsims)
    assert sorted(imts_) == ['PGA', 'SA']
    assert sorted(trts_) == ['active_shallow_crust', 'stable_shallow_crust']
    # now add a new imt and check it's not returned (no matching gsim):
    imt1 = imtcreate(key='IDONTHAVE_GSIMS')
    assert sorted(aval_imts()) == ['PGA', 'SA']
    # but assert we wrote the last imt created:
    assert len(Imt.objects.all()) == 3  # pylint: disable=no-member

    # small test on Tectonic Regions:
    assert not list(aval_trmodels())
    tr_objs = TectonicRegion.objects  # pylint: disable=no-member
    trg1 = tr_objs.create(model='mymodel', geojson='{asc}', type=trt1)
    trg2 = tr_objs.create(model='mymodel', geojson='{asc}', type=trt2)
    assert len(tr_objs.all()) == 2
    assert list(aval_trmodels()) == ['mymodel']
