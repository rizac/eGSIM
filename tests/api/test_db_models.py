"""
Tests the eGSIM Django commands

Created on 6 Apr 2019

@author: riccardo
"""
import pytest
from egsim.api import models
from django.db import IntegrityError

from egsim.smtk.flatfile.columns import ColumnType


@pytest.mark.django_db(transaction=True)  # https://stackoverflow.com/a/54563945
def test_models(capfd):
    """Test the models after initializing the DB with eGSIM management commands"""
    pass