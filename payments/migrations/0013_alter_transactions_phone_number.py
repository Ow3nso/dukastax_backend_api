# Generated by Django 5.0.1 on 2024-08-12 12:46

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0012_transactions_payment_method"),
    ]

    operations = [
        migrations.AlterField(
            model_name="transactions",
            name="phone_number",
            field=models.BigIntegerField(blank=True, null=True),
        ),
    ]
