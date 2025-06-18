from rest_framework import serializers
from app.models import UserProfile
from .models import KYCRequest
from .services.validators import validate_document_type, validate_document_size

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = '__all__'


class KYCRequestSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)

    # Auto-filled fields from UserProfile
    full_name = serializers.CharField(required=False, read_only=True)
    country = serializers.CharField(required=False, read_only=True)

    # Dropbox File URLs (Read-only since files are uploaded externally)
    id_document = serializers.CharField(read_only=True)
    selfie = serializers.CharField(read_only=True)
    address_document = serializers.CharField(read_only=True)

    # Timestamps (Read-only)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)
    reviewed_at = serializers.DateTimeField(read_only=True)
    reviewed_by = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = KYCRequest
        fields = [
            'user', 'full_name', 'date_of_birth', 'address', 'country',
            'id_document', 'selfie', 'address_document', 'status', 'rejection_reason',
            'created_at', 'updated_at', 'reviewed_at', 'reviewed_by'
        ]
        read_only_fields = [
            'user', 'full_name', 'country', 'id_document', 'selfie', 'address_document',
            'created_at', 'updated_at', 'reviewed_at', 'reviewed_by'
        ]

    def create(self, validated_data):
        """
        Override create to ensure user is automatically set and external file URLs are used.
        """
        user_profile = self.context['request'].user.userprofile
        validated_data['user'] = user_profile

        return super().create(validated_data)

    def to_representation(self, instance):
        """
        Auto-fill profile data from the user profile and generate private Dropbox URLs.
        """
        representation = super().to_representation(instance)
        user_profile = instance.user  # UserProfile

        # Ensure only relevant fields are added
        representation.update({
            'full_name': user_profile.full_name,
            'country': user_profile.country,
            'user': str(user_profile.id),
        })

        # Generate signed URLs for documents
        dropbox_service = DropboxService.get_instance()
        if instance.id_document:
            representation['id_document'] = dropbox_service.get_temporary_link(instance.id_document)
        if instance.selfie:
            representation['selfie'] = dropbox_service.get_temporary_link(instance.selfie)
        if instance.address_document:
            representation['address_document'] = dropbox_service.get_temporary_link(instance.address_document)

        return representation
