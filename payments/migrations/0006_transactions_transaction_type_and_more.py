# Generated by Django 5.0.1 on 2024-08-04 07:22

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0005_transactions_invoice_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="transactions",
            name="transaction_type",
            field=models.CharField(
                blank=True,
                choices=[("withdrawal", "Withdrawal"), ("deposit", "Deposit")],
                max_length=10,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="transactions",
            name="api_ref",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name="transactions",
            name="user_id",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]