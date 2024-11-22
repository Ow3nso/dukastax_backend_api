# ----- 3rd Party Libraries -----
from rest_framework import serializers

# ----- In-Built Libraries -----
from .models import Transactions

# ----- Serializers -----
class PinSerializer(serializers.Serializer):
    pin = serializers.CharField(max_length=4, write_only=True)
    user_id = serializers.CharField(max_length=100)

class ConfirmPinSerializer(serializers.Serializer):
    pin = serializers.CharField(max_length=4, write_only=True)
    user_id = serializers.CharField(max_length=100)

class TransactionSerializer(serializers.ModelSerializer):
    # createdAt = serializers.DateTimeField(format='iso-8601')  # Default
#     createdAt = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S')  # Custom ISO format
    # createdAt = serializers.DateTimeField(format=None)  # Unix timestamp

    # updatedAt = serializers.DateTimeField(format='iso-8601')
#     updatedAt = serializers.DateTimeField(format='%Y-%m-%d %H:%M:%S')
    # updatedAt = serializers.DateTimeField(format=None)  # Unix timestamp

    class Meta:
        model = Transactions
        exclude = ('createdAt', 'updatedAt')