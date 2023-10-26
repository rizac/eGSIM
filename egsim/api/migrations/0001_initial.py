# Generated by Django 4.1.5 on 2023-10-25 14:58

from django.db import migrations, models


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
                ('hidden', models.BooleanField(default=False, help_text='Hide this item. This will make the item publicly unavailable through the `names`and `items` properties (which are supposed to be used to publicly expose API). This field is intended to temporarily hide/show items quickly from the admin panel without executing management scrips')),
                ('display_name', models.TextField(default=None, null=True)),
                ('url', models.URLField(default=None, null=True)),
                ('license', models.TextField(default=None, null=True)),
                ('citation', models.TextField(default=None, help_text='Bibliographic citation, as text', null=True)),
                ('doi', models.TextField(default=None, null=True)),
                ('filepath', models.TextField(unique=True)),
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
                ('hidden', models.BooleanField(default=False, help_text='Hide this item. This will make the item publicly unavailable through the `names`and `items` properties (which are supposed to be used to publicly expose API). This field is intended to temporarily hide/show items quickly from the admin panel without executing management scrips')),
                ('unverified', models.BooleanField(default=False, help_text='not independently verified')),
                ('experimental', models.BooleanField(default=False, help_text='experimental, may change in future versions')),
                ('adapted', models.BooleanField(default=False, help_text='not intended for general use, the behaviour may not be as expected')),
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
                ('hidden', models.BooleanField(default=False, help_text='Hide this item. This will make the item publicly unavailable through the `names`and `items` properties (which are supposed to be used to publicly expose API). This field is intended to temporarily hide/show items quickly from the admin panel without executing management scrips')),
                ('display_name', models.TextField(default=None, null=True)),
                ('url', models.URLField(default=None, null=True)),
                ('license', models.TextField(default=None, null=True)),
                ('citation', models.TextField(default=None, help_text='Bibliographic citation, as text', null=True)),
                ('doi', models.TextField(default=None, null=True)),
                ('filepath', models.TextField(unique=True)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddIndex(
            model_name='gsim',
            index=models.Index(fields=['name'], name='api_gsim_name_309dde_idx'),
        ),
    ]
