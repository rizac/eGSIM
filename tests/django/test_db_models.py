"""
Tests the eGSIM Django DB models

Created on 6 Apr 2019

@author: riccardo
"""
import pytest

from egsim.api.models import Gsim


@pytest.mark.django_db(transaction=True)  # https://stackoverflow.com/a/54563945
def test_models(capfd):
    """Test the models methods after egsim commands are run and the DB populated"""

    objects = sorted(Gsim.objects.all(), key=lambda _: _.name)
    # assert we created an id attr and a name attr they are all unique:
    assert len({_.id for _ in objects}) == len(objects)
    assert len({_.name for _ in objects}) == len(objects)
    # get names:
    names = sorted(Gsim.names())
    # assert names are all strings:
    assert all(isinstance(_, str) for _ in names)
    # assert names returns the same as `objects`
    assert names == [_.name for _ in objects]
    # use queryset now:
    queryset = sorted(Gsim.queryset(), key=lambda _: _.name)
    assert [_.id for _ in queryset] == [_.id for _ in objects]  # noqa

    # Now let's create an hidden item, as we clicked on the admin panel:
    assert not objects[0].hidden
    objects[0].hidden = True
    objects[0].save()
    assert objects[0].hidden
    hidden_name = objects[0].name

    # re check
    old_objects = objects
    objects = sorted(Gsim.objects.all(), key=lambda _: _.name)
    # assert we created an id attr and a name attr they are all unique:
    assert len({_.id for _ in objects}) == len(objects)
    assert len({_.name for _ in objects}) == len(objects)
    # assert the objects are the same as before
    assert [_.id for _ in old_objects] == [_.id for _ in objects]
    # get names:
    names = sorted(Gsim.names())
    # assert names returns the same as `objects` but not hidden name
    assert len(names) == len(objects) -1
    assert names == [_.name for _ in objects if _.name != hidden_name]
    # use queryset now and assert we do not have hidden_name either:
    queryset = sorted(Gsim.queryset(), key=lambda _: _.name)
    assert len(queryset) == len(names)
    assert [_.id for _ in queryset] == [_.id for _ in objects if _.name != hidden_name]  # noqa
