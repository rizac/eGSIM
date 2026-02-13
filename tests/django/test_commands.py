"""
Tests the eGSIM Django commands

Created on 6 Apr 2019

@author: riccardo
"""
import os
from unittest.mock import patch

from django.conf import settings

import pytest
from django.core.management import call_command

import pandas as pd
import yaml

from egsim.api.models import Gsim
from egsim.smtk.flatfile import get_dtype_of


@pytest.mark.django_db
def test_initdb(capsys):
    """Test the command initializing the DB with eGSIM data"""

    # NOTE: the decorator `django_db` already executes the command below
    # (django_db uses the fixture django_db_setup, overridden in conftest.py)
    # Here we provide capsys in case we want to test the generated output
    # in more details
    call_command('egsim-init', interactive=False)
    captured = capsys.readouterr()
    capout = captured.out
    assert capout and "Unused Flatfile column(s)" not in capout
    media_root = settings.MEDIA_ROOT
    with open(os.path.join(media_root, "media_files.yml")) as _:
        data = yaml.safe_load(_)
        for ff in data:
            if os.path.basename(os.path.dirname(ff)) == 'flatfiles':
                dfr: pd.DataFrame = pd.read_hdf(os.path.join(media_root, ff))  # noqa
                assert all(get_dtype_of(dfr[c]) is not None for c in dfr.columns)


@pytest.mark.django_db
@patch(
    "builtins.input",
    side_effect=[
        "flatfile",
        "invalid_column 23",
        "<",
        "gsim",
        "",
        "name ^BindiEtAl2014Rjb$",
        "hidden true",
        "q"
    ]
)
def test_egsimdb(mocked_input, capsys):
    """Test the command for hiding showing items in the eGSIM db"""

    # NOTE: the decorator `django_db` already executes the command below
    # (django_db uses the fixture django_db_setup, overridden in conftest.py)
    # Here we provide capsys in case we want to test the generated output
    # in more details
    assert 'BindiEtAl2014Rjb' in set(Gsim.names())  # also test names() attr
    call_command('egsim-db')
    out_err = capsys.readouterr()
    # now the model should be hidden (test `queryset` this time instead of `names()`)
    assert Gsim.queryset('name').filter(name='BindiEtAl2014Rjb').count() == 0
    assert "No matching column: \"invalid_column\"" in out_err.out
    # assert 'Aborted by user' not in capsys.readouterr().out
    # call_command('egsim-db')
    assert 'Command terminated' in out_err.out


@pytest.mark.django_db
def test_collectstatic(settings, tmp_path):
    import shutil

    # Override STATIC_ROOT for this test
    settings.STATIC_ROOT = tmp_path

    # Ensure STATIC_ROOT is empty
    if tmp_path.exists():
        shutil.rmtree(tmp_path)
    tmp_path.mkdir()

    # Run collectstatic non-interactively
    call_command("collectstatic", interactive=False, clear=True)

    expected = [
        # 'admin',  # <- this dir is not collected anymore (APP in settings removed)
        'css', 'img', 'js'
    ]
    assert sorted(os.listdir(tmp_path)) == expected

    assert all(os.path.isdir(os.path.join(tmp_path, _)) for _ in expected)

    assert all(
        len(os.listdir(os.path.join(tmp_path, _)))
        for _ in expected
    )
