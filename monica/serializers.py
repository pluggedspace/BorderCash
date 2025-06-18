from rest_framework import serializers
from .models import Dispute, FAQ
import uuid

class DisputeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dispute
        fields = ['id', 'description', 'transaction_id', 'category', 'status', 'user', 'created_at']
        read_only_fields = ['user', 'category', 'status']

    def validate_transaction_id(self, value):
        """Ensure transaction_id is a valid UUID string."""
        try:
            uuid.UUID(str(value))  # Attempt to convert to UUID
        except ValueError:
            raise serializers.ValidationError("Transaction ID must be a valid UUID.")
        return value

class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ['question', 'answer']
