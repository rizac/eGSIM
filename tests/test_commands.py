"""
Tests the eGSIM Django commands

Created on 6 Apr 2019

@author: riccardo
"""
from json import JSONEncoder
import pytest
from unittest.mock import patch

from egsim.api import models
from egsim.api.flatfile import read_flatfile

from django.core.management import call_command
from django.db import IntegrityError


@pytest.mark.django_db(transaction=True)  # https://stackoverflow.com/a/54563945
def test_initdb(capfd, tmpdir):
    """Test initdb command."""
    # @pytest.mark.django_db makes already all operations we need. We anyway check
    # that all __str__ method of our classes work. The __str__ methods are shown in
    # the admin panel but not used elsewhere

    # load ESM flatfile to see it's there:
    # dfr = read_flatfile(join(FlatfileCommand.dest_dir(), 'esm2018.hdf'))
    # assert len(dfr.columns) == 83
    # assert len(dfr) == 23014

    for _name in dir(models):
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

    # captured = capfd.readouterr()
    # assert not captured.err
    # sout = captured.out


def testJSONEncoder():
    class DTEncoder(JSONEncoder):

        def default(self, d):
            return d.isoformat(sep='T')

    val = JSONEncoder(default=lambda d: d.isoformat('T')).encode('a')
    val = DTEncoder().encode('a')

    class MyObj:
        pass

    a = MyObj()
    with pytest.raises(Exception) as exc:
        val = JSONEncoder(default=lambda d: d.isoformat('T')).encode(a)

    with pytest.raises(Exception) as exc:
        val = DTEncoder().encode(a)

    asd = 9


@pytest.mark.django_db
def test_initdb_gsim_required_attrs_not_defined(capsys):
    """Test initdb command, with new Gsims and required attributes not
    managed by egsim"""
    # why is it @patch not working if provided as decorator?
    # It has conflicts with capsys fixture, but only here ....
    # Anyway:
    with patch('api.management.commands.initdb.'
               'get_gsim_required_attrs_dict',
               return_value={'rjb': 'rjb'}) as _:
        call_command('initdb')
        captured = capsys.readouterr()
        capout = captured.out
        assert 'WARNING: ' in capout

    for key in ['vs30measured', 'ztor', 'dip']:
        assert "%s (defined for " % key in capout
    assert "rjb" not in capout


# @pytest.mark.parametrize('input_flatfile_name, sep',
#                          [('egsim_flatfile_marmara_event_26092019_nobom.csv', 'comma'),
#                           ('egsim_flatfile_marmara_event_26092019.csv', 'comma'),
#                           ('esm_sa_flatfile_2018.csv', None)])
# @patch('egsim.management.commands.gmdb.get_gmdb_path')
# @patch('egsim.management.commands.gmdb.input')
# def test_gmdb_esm(mock_input,
#                   mock_get_gmdb_path,
#                   input_flatfile_name, sep,
#                   # pytest fixtures:
#                   testdata, capsys):
#     """Test gmdb_esm command (and consequently, also gmbd command)"""
#     ffname = input_flatfile_name
#     ffpath = testdata.path(ffname)
#     outdir = testdata.path('gmdb')
#     outpath = os.path.join(outdir, os.path.splitext(ffname)[0] + '.hdf5')
#     assert not os.path.isfile(outpath)
#     mock_get_gmdb_path.return_value = outdir
#     try:
#         # not specifying arguments:
#         with pytest.raises(CommandError) as cerr:
#             _ = call_command('gmdb_esm')
#         assert 'the following arguments are required: flatfile' in \
#             str(cerr)
#
#         mock_input.return_value = ''
#         # we decide NOT to create the dir:
#         with pytest.raises(CommandError) as cerr:
#             _ = call_command('gmdb_esm',  ffpath)
#         assert 'Operation aborted by user' in \
#             str(cerr)
#         # now we anser 'yes' to the create dir:
#         mock_input.return_value = 'y'
#
#         # specifying duplicated arguments:
#         with pytest.raises(CommandError) as cerr:
#             _ = call_command('gmdb_esm', ffpath, ffpath)
#         assert 'flatfile is specified more than once' in \
#             str(cerr)
#
#         # ok, normal case:
#         if sep is None:
#             _ = call_command('gmdb_esm',  ffpath)
#         else:
#             _ = call_command('gmdb_esm', ffpath, sep=sep)
#         assert os.path.isfile(outpath)
#         captured = capsys.readouterr()
#         assert not captured.err
#         sout = captured.out
#         # try to remove the file: not permitted:
#         assert os.access(outpath, os.R_OK)
#         # this is False if you are testing from root, as root has always
#         # write privileges: https://stackoverflow.com/a/27747471
#         # Thus this MIGHT not work:
#         # assert not os.access(outpath, os.W_OK)
#         # therefore
#         assert not os.stat(outpath).st_mode & S_IWUSR
#         assert not os.stat(outpath).st_mode & S_IWGRP
#         assert not os.stat(outpath).st_mode & S_IWOTH
#
#         # now that the file exists, test that overwriting on the same
#         # db raises:
#         with pytest.raises(CommandError) as cerr:
#             _ = call_command('gmdb_esm',  ffpath)
#         assert 'No flatfile to parse' in str(cerr)
#
#     finally:
#         if os.path.isfile(outpath):
#             os.remove(outpath)
#         if os.path.isdir(outdir):
#             os.rmdir(outdir)
