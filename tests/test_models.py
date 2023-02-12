"""
Tests the eGSIM Django commands

Created on 6 Apr 2019

@author: riccardo
"""
import pytest
from egsim.api import models
from django.db import IntegrityError


@pytest.mark.django_db(transaction=True)  # https://stackoverflow.com/a/54563945
def test_models(capfd):
    """Test the models after initializing the DB with eGSIM management commands"""

    # load ESM flatfile to see it's there:
    # dfr = read_flatfile(join(FlatfileCommand.dest_dir(), 'esm2018.hdf'))
    # assert len(dfr.columns) == 83
    # assert len(dfr) == 23014

    for _name in dir(models):
        # check the __str__ method of the 1st instance of each models.Model. This is
        # to assure the admin panel (which usually uses it) works correctly
        _ = getattr(models, _name)
        try:
            is_class = issubclass(_, models.Model) and not _._meta.abstract and \
                _ not in (models.Model, models._UniqueNameModel)
        except:  # noqa
            is_class = False
        if is_class:
            print()
            print(str(_) + ' 1st Instance to string:')
            inst = _.objects.all().first()
            print(str(inst))

    f = models.FlatfileColumn(name='rx_1_1', oq_name='ert_1',
                              category=models.FlatfileColumn.Category.RUPTURE_PARAMETER)
    f.save()
    assert f.category == models.FlatfileColumn.Category.RUPTURE_PARAMETER == \
           models.FlatfileColumn.Category.RUPTURE_PARAMETER.value == 1

    f = models.FlatfileColumn(name='rx_1', oq_name='ert')
    f.save()
    assert f.category is None

    with pytest.raises(Exception) as ierr:
        models.FlatfileColumn(name='rx', oq_name='ert').save()  # name not unique
    assert 'name' in str(ierr.value)

    with pytest.raises(Exception) as ierr:
        # oq_name + category not unique:
        models.FlatfileColumn(name='bla', oq_name='rx',
                              category=models.FlatfileColumn.Category.DISTANCE_MEASURE).save()
    assert 'oq_name' in str(ierr.value)

    akkarbommer = models.Gsim.objects.filter(name__exact='AkkarBommer2010').first()
    geom = {'type': 'Polygon', 'coordinates': [[[]]]}
    with pytest.raises(IntegrityError) as ierr:
        # already exist:
        regio = models.Regionalization.objects.filter(name='share').get()
        models.GsimRegion(gsim=akkarbommer, geometry=geom,
                          regionalization=regio).save()
    assert 'unique constraint' in str(ierr.value).lower()

    with pytest.raises(IntegrityError) as ierr:
        # geom type false:
        geom['type'] = 'invalid'
        # create a valid and new RegionalizationDataSource to avoid Unique Constraints:
        regio2, _ = models.Regionalization.objects.get_or_create(name='share2')
        models.GsimRegion(gsim=akkarbommer, geometry=geom,
                          regionalization=regio2).save()
    assert str(models.GsimRegion.GEOM_TYPES) in str(ierr.value)
