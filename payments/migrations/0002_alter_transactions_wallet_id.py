# Generated by Django 5.0.7 on 2024-07-15 09:19

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="transactions",
            name="wallet_id",
            field=models.CharField(max_length=100, null=True),
        ),
    ]
