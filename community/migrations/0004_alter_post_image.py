# Generated by Django 5.0.6 on 2024-07-13 06:52

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("community", "0003_comment_parent"),
    ]

    operations = [
        migrations.AlterField(
            model_name="post",
            name="image",
            field=models.ImageField(blank=True, null=True, upload_to="post/"),
        ),
    ]
