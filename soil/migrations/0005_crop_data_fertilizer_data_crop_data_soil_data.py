# Generated by Django 5.0.6 on 2024-07-15 01:07

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("soil", "0004_crop_data_created_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="crop_data",
            name="fertilizer_data",
            field=models.JSONField(default=dict),
        ),
        migrations.AddField(
            model_name="crop_data",
            name="soil_data",
            field=models.JSONField(default=dict),
        ),
    ]
