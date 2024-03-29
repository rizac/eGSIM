# Generated by Django 4.1.5 on 2023-03-15 07:16

from django.db import migrations, models
import django.db.models.deletion
import egsim.api.models
import egsim.smtk.flatfile


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Flatfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField(help_text='Unique name', unique=True)),
                ('display_name', models.TextField(default=None, null=True)),
                ('url', models.URLField(default=None, null=True)),
                ('license', models.TextField(default=None, null=True)),
                ('citation', models.TextField(default=None, help_text='Bibliographic citation, as text', null=True)),
                ('doi', models.TextField(default=None, null=True)),
                ('filepath', models.TextField(unique=True)),
                ('hidden', models.BooleanField(default=False, help_text='if true, the flatfile is hidden in browsers (users can still access it via API requests, if not expired)')),
                ('expiration', models.DateTimeField(default=None, help_text='expiration date(time). If null, the flatfile has no expiration date', null=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='FlatfileColumn',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField(help_text='Unique name', unique=True)),
                ('oq_name', models.TextField(help_text='The OpenQuake name of the GSIM property associated to this column (e.g., as used in Contexts during residuals computation)', null=True)),
                ('type', models.SmallIntegerField(choices=[(0, 'rupture parameter'), (1, 'site parameter'), (2, 'distance measure'), (3, 'imt'), (4, 'unknown')], default=egsim.smtk.flatfile.ColumnType['unknown'], help_text='The type of Column of this column (e.g., IMT, OpenQuake parameter, distance measure)')),
                ('help', models.TextField(default='', help_text='Field help text')),
                ('data_properties', models.JSONField(decoder=egsim.api.models.DateTimeDecoder, encoder=egsim.api.models.DateTimeEncoder, help_text='The properties of the this column data, as JSON (null: no properties). Optional keys: "dtype" ("int", "bool", "datetime", "str" or "float", or list of possible values the column data can have), "bounds": [min or null, max or null] (null means: unbounded), "default" (the default when missing), "required" (bool)', null=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Gsim',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField(help_text='Unique name', unique=True)),
                ('init_parameters', models.JSONField(encoder=egsim.api.models.CompactEncoder, help_text='The parameters used to initialize this GSIM in Python, as JSON object of names mapped to their default value. Included here are only parameters whose default value type is a Python int, float, bool or str', null=True)),
                ('warning', models.TextField(default=None, help_text='Optional usage warning(s) to be reported before usage (e.g., in GUIs)', null=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='GsimRegion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('geometry', models.JSONField(encoder=egsim.api.models.CompactEncoder, help_text='The region area as geoJSON Geometry object, with at least the keys "coordinates"and "type\'" (usually \'Polygon\', \'MultiPolygon\'). For details see: https://en.wikipedia.org/wiki/GeoJSON#Geometries)')),
            ],
        ),
        migrations.CreateModel(
            name='GsimWithError',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField(help_text='Unique name', unique=True)),
                ('error_type', models.TextField(help_text='Error type, usually the class name of the Exception raised')),
                ('error_message', models.TextField(help_text='Error message')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Imt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField(help_text='Unique name', unique=True)),
                ('needs_args', models.BooleanField(default=False)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Regionalization',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField(help_text='Unique name', unique=True)),
                ('display_name', models.TextField(default=None, null=True)),
                ('url', models.URLField(default=None, null=True)),
                ('license', models.TextField(default=None, null=True)),
                ('citation', models.TextField(default=None, help_text='Bibliographic citation, as text', null=True)),
                ('doi', models.TextField(default=None, null=True)),
                ('geometry', models.JSONField(encoder=egsim.api.models.CompactEncoder, help_text='The region area as geoJSON Geometry object, with at least the keys "coordinates"and "type\'" (usually \'Polygon\', \'MultiPolygon\'). For details see: https://en.wikipedia.org/wiki/GeoJSON#Geometries)')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddIndex(
            model_name='imt',
            index=models.Index(fields=['name'], name='api_imt_name_621eda_idx'),
        ),
        migrations.AddField(
            model_name='gsimregion',
            name='gsim',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='regions', to='api.gsim'),
        ),
        migrations.AddField(
            model_name='gsimregion',
            name='regionalization',
            field=models.ForeignKey(help_text='The name of the seismic hazard source regionalization that defines and includes this region', null=True, on_delete=django.db.models.deletion.SET_NULL, to='api.regionalization', to_field='name'),
        ),
        migrations.AddField(
            model_name='gsim',
            name='imts',
            field=models.ManyToManyField(help_text='Intensity Measure Type(s)', related_name='gsims', to='api.imt'),
        ),
        migrations.AddField(
            model_name='gsim',
            name='required_flatfile_columns',
            field=models.ManyToManyField(help_text='Required flatfile column(s)', related_name='gsims', to='api.flatfilecolumn'),
        ),
        migrations.AddIndex(
            model_name='flatfilecolumn',
            index=models.Index(fields=['name'], name='api_flatfil_name_a9ce2a_idx'),
        ),
        migrations.AddConstraint(
            model_name='gsimregion',
            constraint=models.UniqueConstraint(fields=('gsim', 'regionalization'), name='api_gsimregion_unique_gsim_and_regionalization'),
        ),
        migrations.AddIndex(
            model_name='gsim',
            index=models.Index(fields=['name'], name='api_gsim_name_309dde_idx'),
        ),
    ]
