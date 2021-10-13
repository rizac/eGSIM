# Generated by Django 3.2.8 on 2021-10-13 22:17

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('egsim', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='GsimAttribute',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField(help_text='Unique name', unique=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='GsimDistance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField(help_text='Unique name', unique=True)),
                ('flatfile_column', models.TextField(help_text='The corresponding flat file column name (Null: no mapping)', null=True, unique=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='GsimRuptureParam',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField(help_text='Unique name', unique=True)),
                ('flatfile_column', models.TextField(help_text='The corresponding flat file column name (Null: no mapping)', null=True, unique=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='GsimSitesParam',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField(help_text='Unique name', unique=True)),
                ('flatfile_column', models.TextField(help_text='The corresponding flat file column name (Null: no mapping)', null=True, unique=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='GsimTrt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.TextField(help_text='Unique name', unique=True)),
            ],
            options={
                'abstract': False,
            },
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
            name='Region',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('regionalization', models.TextField(help_text='The name of the parent regionalization (e.g., SHARE, ESHM20, germany)')),
                ('name', models.TextField(help_text='The region name')),
                ('geometry', models.JSONField(help_text='The region coordinates as geoJSON Geometry object, i.e. with at least the "type\'" and "coordinates" fields (https://en.wikipedia.org/wiki/GeoJSON#Geometries)')),
            ],
        ),
        migrations.CreateModel(
            name='RegionGsimMapping',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
        ),
        migrations.DeleteModel(
            name='Error',
        ),
        migrations.RemoveField(
            model_name='gsim',
            name='key',
        ),
        migrations.RemoveField(
            model_name='gsim',
            name='needs_args',
        ),
        migrations.RemoveField(
            model_name='imt',
            name='key',
        ),
        migrations.AddField(
            model_name='gsim',
            name='name',
            field=models.TextField(default='', help_text='Unique name', unique=True),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='imt',
            name='name',
            field=models.TextField(default='', help_text='Unique name', unique=True),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='gsim',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.AlterField(
            model_name='gsim',
            name='imts',
            field=models.ManyToManyField(help_text='Intensity Measure Type(s)', related_name='gsims', to='egsim.Imt'),
        ),
        migrations.AlterField(
            model_name='gsim',
            name='warning',
            field=models.TextField(default=None, help_text='Optional usage warning(s)', null=True),
        ),
        migrations.AlterField(
            model_name='imt',
            name='id',
            field=models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID'),
        ),
        migrations.DeleteModel(
            name='TectonicRegion',
        ),
        migrations.AddField(
            model_name='regiongsimmapping',
            name='gsim',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='regions', to='egsim.gsim'),
        ),
        migrations.AddField(
            model_name='regiongsimmapping',
            name='region',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='gsims', to='egsim.region'),
        ),
        migrations.AddConstraint(
            model_name='region',
            constraint=models.UniqueConstraint(fields=('regionalization', 'name'), name='unique(regionalization,name)'),
        ),
        migrations.AddField(
            model_name='gsim',
            name='attributes',
            field=models.ManyToManyField(help_text='Required attribute(s)', related_name='gsims', to='egsim.GsimAttribute'),
        ),
        migrations.AddField(
            model_name='gsim',
            name='distances',
            field=models.ManyToManyField(help_text='Required distance(s)', related_name='gsims', to='egsim.GsimDistance'),
        ),
        migrations.AddField(
            model_name='gsim',
            name='rupture_parameters',
            field=models.ManyToManyField(help_text='Required rupture parameter(s)', related_name='gsims', to='egsim.GsimRuptureParam'),
        ),
        migrations.AddField(
            model_name='gsim',
            name='sites_parameters',
            field=models.ManyToManyField(help_text='Required site parameter(s)', related_name='gsims', to='egsim.GsimSitesParam'),
        ),
        migrations.AlterField(
            model_name='gsim',
            name='trt',
            field=models.ForeignKey(help_text='Tectonic Region type', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='gsims', to='egsim.gsimtrt'),
        ),
        migrations.DeleteModel(
            name='Trt',
        ),
        migrations.AddConstraint(
            model_name='regiongsimmapping',
            constraint=models.UniqueConstraint(fields=('gsim', 'region'), name='unique(gsim,region)'),
        ),
    ]
