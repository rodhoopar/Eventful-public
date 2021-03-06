# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-05-10 00:44
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eventful', '0014_auto_20170505_2109'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='highPriority',
            field=models.PositiveSmallIntegerField(default=20, verbose_name='High'),
        ),
        migrations.AlterField(
            model_name='event',
            name='lowPriority',
            field=models.PositiveSmallIntegerField(default=40, verbose_name='Low'),
        ),
    ]
