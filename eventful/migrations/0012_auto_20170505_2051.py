# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-05-05 20:51
from __future__ import unicode_literals

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eventful', '0011_auto_20170505_2045'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='event',
            name='total_responsetime',
        ),
        migrations.AddField(
            model_name='event',
            name='avg_responsetime',
            field=models.PositiveIntegerField(default=0, verbose_name='Average Response Time'),
        ),
        migrations.AlterField(
            model_name='event',
            name='latest_assignment',
            field=models.DateTimeField(default=datetime.datetime.now, verbose_name='Time of Latest Assignment'),
        ),
    ]
