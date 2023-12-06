"""
Tests the eGSIM Django commands

Created on 6 Apr 2019

@author: riccardo
"""
import pytest

from egsim.api.models import Gsim


@pytest.mark.django_db(transaction=True)  # https://stackoverflow.com/a/54563945
def test_models(capfd):
    """Test the models after initializing the DB with eGSIM management commands"""

    models = list(Gsim.objects.all())
    names = sorted(Gsim.names())
    assert all(isinstance(_, str) for _ in names)
    assert sorted(names) == sorted(_.name for _ in models)
    name = models[0].name
    assert sorted(_.name for _ in Gsim.queryset('name')) == names
    assert sorted(_.name for _ in Gsim.queryset()) == names
    # save to Db one hidden:
    assert not models[0].hidden
    models[0].hidden = True
    models[0].save()
    # re check
    models2 = list(Gsim.objects.all())
    assert sorted(_.name for _ in models) == sorted(_.name for _ in models2)
    names2 = sorted(Gsim.names())
    assert len(names2) == len(models) - 1
    assert sorted(_.name for _ in models if _.name != name) == names2
    assert sorted(_.name for _ in Gsim.queryset('name')) == names2
    assert sorted(_.name for _ in Gsim.queryset()) == names2