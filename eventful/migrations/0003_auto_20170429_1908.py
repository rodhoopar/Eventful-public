# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-04-29 19:08
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eventful', '0002_auto_20170428_0336'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='name',
            field=models.TextField(max_length=50, verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='task',
            name='status',
            field=models.TextField(default='Pending', verbose_name='Status'),
        ),
        migrations.AlterField(
            model_name='volunteer',
            name='category',
            field=models.TextField(blank=True, null=True, verbose_name='Category (Optional)'),
        ),
        migrations.AlterField(
            model_name='volunteer',
            name='name',
            field=models.TextField(verbose_name='Name'),
        ),
        migrations.AlterField(
            model_name='volunteer',
            name='phone',
            field=models.TextField(unique=True, verbose_name='Phone Number'),
        ),
        migrations.AlterField(
            model_name='volunteer',
            name='status',
            field=models.TextField(default='Free', verbose_name='Status'),
        ),
    ]
