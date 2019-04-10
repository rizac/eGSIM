# Generated by Django 2.0.13 on 2019-04-07 12:43

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Error',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('entity_key', models.TextField(unique=True)),
                ('entity_type', models.CharField(choices=[('gsim', 'Ground Shaking Intensity Model'), ('imt', 'Intensity Measure Type'), ('trt', 'Tectonic Region Type')], max_length=4)),
                ('type', models.TextField()),
                ('message', models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name='Gsim',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.TextField(unique=True)),
                ('needs_args', models.BooleanField(default=False)),
                ('warning', models.TextField(default=None, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Imt',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=100, unique=True)),
                ('needs_args', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='TectonicRegion',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('model', models.TextField()),
                ('geojson', models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='Trt',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.TextField(unique=True)),
                ('oq_att', models.CharField(max_length=100, unique=True)),
                ('oq_name', models.TextField(unique=True)),
            ],
        ),
        migrations.AddField(
            model_name='tectonicregion',
            name='type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='egsim.Trt'),
        ),
        migrations.AddField(
            model_name='gsim',
            name='imts',
            field=models.ManyToManyField(related_name='gsims', to='egsim.Imt'),
        ),
        migrations.AddField(
            model_name='gsim',
            name='trt',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='egsim.Trt'),
        ),
    ]
