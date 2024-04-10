"""
Tests the eGSIM Django commands

Created on 6 Apr 2019

@author: riccardo
"""
import os
from django.conf import settings

import pytest
from django.core.management import call_command

import pandas as pd

from egsim.smtk.flatfile import get_dtype_of


@pytest.mark.django_db
def test_initdb(capsys):
    """Test the command initializing the DB with eGSIM data"""
    # NOTE: the decorator `django_db` already executes the command below
    # (django_db uses the fixture django_db_setup, overridden in conftest.py)
    # Here we provide capsys in case we want to test the generated output
    # in more details
    call_command('egsim_init', interactive=False)
    captured = capsys.readouterr()
    capout = captured.out
    assert capout and "Unused Flatfile column(s)" not in capout
    flatfiles_dir = os.path.join(settings.MEDIA_ROOT, 'flatfiles')
    for ff in os.listdir(flatfiles_dir):
        dfr: pd.DataFrame = pd.read_hdf(os.path.join(flatfiles_dir, ff))  # noqa
        assert all(get_dtype_of(dfr[c]) is not None for c in dfr.columns)
