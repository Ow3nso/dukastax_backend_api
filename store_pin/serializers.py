# ----- 3rd Party Libraries -----
from rest_framework import serializers

# ----- Serializers -----
class PinSerializer(serializers.Serializer):
    pin = serializers.CharField(max_length=4, write_only=True)
    user_id = serializers.CharField(max_length=100)

class ConfirmPinSerializer(serializers.Serializer):
    pin = serializers.CharField(max_length=4, write_only=True)
    user_id = serializers.CharField(max_length=100)