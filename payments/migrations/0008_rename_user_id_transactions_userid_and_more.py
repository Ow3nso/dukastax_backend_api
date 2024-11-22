# Generated by Django 5.0.1 on 2024-08-09 11:25

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0007_transactions_card_number_transactions_cvv_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="transactions",
            old_name="user_id",
            new_name="userId",
        ),
        migrations.RemoveField(
            model_name="transactions",
            name="api_ref",
        ),
        migrations.RemoveField(
            model_name="transactions",
            name="card_number",
        ),
        migrations.RemoveField(
            model_name="transactions",
            name="cvv",
        ),
        migrations.RemoveField(
            model_name="transactions",
            name="expiry_month",
        ),
        migrations.RemoveField(
            model_name="transactions",
            name="expiry_year",
        ),
        migrations.RemoveField(
            model_name="transactions",
            name="invoice_id",
        ),
        migrations.RemoveField(
            model_name="transactions",
            name="state",
        ),
        migrations.RemoveField(
            model_name="transactions",
            name="transaction_type",
        ),
        migrations.AddField(
            model_name="transactions",
            name="createdAt",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name="transactions",
            name="currency",
            field=models.CharField(
                blank=True,
                choices=[("KES", "KES"), ("USD", "USD")],
                max_length=3,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="transactions",
            name="description",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name="transactions",
            name="imageUrl",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AddField(
            model_name="transactions",
            name="newBalance",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True
            ),
        ),
        migrations.AddField(
            model_name="transactions",
            name="reference",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=10, null=True
            ),
        ),
        migrations.AddField(
            model_name="transactions",
            name="shopId",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="transactions",
            name="status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("PROCESSING", "PROCESSING"),
                    ("COMPLETE", "COMPLETE"),
                    ("FAILED", "FAILED"),
                    ("RETRY", "RETRY"),
                ],
                max_length=50,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="transactions",
            name="type",
            field=models.CharField(
                blank=True,
                choices=[("M-PESA", "M-PESA"), ("CARD", "CARD")],
                max_length=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="transactions",
            name="updatedAt",
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name="transactions",
            name="walletId",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
