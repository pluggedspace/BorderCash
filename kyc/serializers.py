from rest_framework import serializers
from app.models import UserProfile
from .models import KYCRequest
from .services.validators import validate_document_type, validate_document_size


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = '__all__'  # Adjust based on what fields you want to expose


class KYCRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYCRequest
        fields = ['user', 'full_name', 'date_of_birth', 'address', 'country',
                  'id_document', 'selfie', 'address_document', 'status', 'rejection_reason']

    def validate_id_document(self, value):
        # Custom validation for ID document
        validate_document_size(value)
        validate_document_type(value)
        return value

    def validate_selfie(self, value):
        # Custom validation for selfie
        validate_document_size(value)
        validate_document_type(value)
        return value

    def validate_address_document(self, value):
        # Custom validation for address proof
        validate_document_size(value)
        validate_document_type(value)
        return value


