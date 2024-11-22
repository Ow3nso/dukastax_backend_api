# ----- 3rd Party Libraries -----
import uuid
from django.db import models

# Create your models here.
class Transactions(models.Model):
    CURRENCY = (
        ('KES', 'KES'),
        ('USD', 'USD'),
    )

    TRANSACTION_TYPE = (
        ('M-PESA', 'M-PESA'),
        ('CARD', 'CARD'),
    )

    PAYMENT_METHOD = (
        ('MOBILE_MONEY', 'MOBILE_MONEY'),
        ('CARD_PAYMENT', 'CARD_PAYMENT'),
    )

    STATUS = (
        ('PENDING', 'PENDING'),
        ('PROCESSING', 'PROCESSING'),
        ('COMPLETE', 'COMPLETE'),
        ('FAILED', 'FAILED'),
        ('RETRY', 'RETRY'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(blank=True, null=True, max_length=3, choices=CURRENCY)
    type = models.CharField(max_length=10, blank=True, null=True, choices=TRANSACTION_TYPE)
    payment_method = models.CharField(max_length=50, blank=True, null=True, choices=PAYMENT_METHOD)
    status = models.CharField(max_length=50, blank=True, null=True, choices=STATUS) 
    phone_number = models.BigIntegerField(blank=True, null=True)
    description = models.CharField(blank=True, null=True, max_length=50)
    imageUrl = models.CharField(max_length=50, blank=True, null=True)
    newBalance = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    reference = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    shopId = models.CharField(max_length=100, blank=True, null=True)
    userId = models.CharField(max_length=100, blank=True, null=True)
    walletId = models.CharField(max_length=100, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True, null=True)
    createdAt = models.DateTimeField(blank=True, null=True, auto_now_add=True)
    updatedAt = models.DateTimeField(blank=True, null=True, auto_now_add=True)
    invoice_id = models.CharField(max_length=50, blank=True, null=True)
    # api_ref = models.CharField(max_length=100, blank=True, null=True)

    # def __str__(self):
    #     return f"{self.transaction_type} of {self.amount} to {self.phone_number}"


class Orders(models.Model):
    CURRENCY = (
        ('KES', 'KES'),
        ('USD', 'USD'),
    )

    TRANSACTION_TYPE = (
        ('M-PESA', 'M-PESA'),
        ('CARD', 'CARD'),
    )

    PAYMENT_METHOD = (
        ('MOBILE_MONEY', 'MOBILE_MONEY'),
        ('CARD_PAYMENT', 'CARD_PAYMENT'),
    )

    STATUS = (
        ('PENDING', 'PENDING'),
        ('PROCESSING', 'PROCESSING'),
        ('COMPLETE', 'COMPLETE'),
        ('FAILED', 'FAILED'),
        ('RETRY', 'RETRY'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(blank=True, null=True, max_length=3, choices=CURRENCY)
    type = models.CharField(max_length=10, blank=True, null=True, choices=TRANSACTION_TYPE)
    payment_method = models.CharField(max_length=50, blank=True, null=True, choices=PAYMENT_METHOD)
    status = models.CharField(max_length=50, blank=True, null=True, choices=STATUS)
    phone_number = models.BigIntegerField(blank=True, null=True)
    description = models.CharField(blank=True, null=True, max_length=50)
    imageUrl = models.CharField(max_length=50, blank=True, null=True)
    newBalance = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    reference = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    shopId = models.CharField(max_length=100, blank=True, null=True)
    userId = models.CharField(max_length=100, blank=True, null=True)
    walletId = models.CharField(max_length=100, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True, null=True)
    createdAt = models.DateTimeField(blank=True, null=True, auto_now_add=True)
    updatedAt = models.DateTimeField(blank=True, null=True, auto_now_add=True)
    invoice_id = models.CharField(max_length=50, blank=True, null=True)
    # new orders fields
    name = models.CharField(max_length=100, blank=True, null=True)
    orderId = models.CharField(max_length=50, blank=True, null=True)
    customerId = models.CharField(max_length=50, blank=True, null=True)
    statusType = models.CharField(max_length=50, blank=True, null=True)
    items = models.JSONField(default=list, blank=True, null=True)