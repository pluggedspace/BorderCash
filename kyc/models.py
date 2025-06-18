import base64
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from dynaconf import ValidationError
from app.models import UserProfile
from django_countries.fields import CountryField
from storages.backends.dropbox import DropboxStorage
import dropbox
from .services.dropbox import DropboxService


class KYCRequest(models.Model):
    # User relationship
    user = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='kyc_requests'
    )

    # Personal information
    full_name = models.CharField(max_length=255, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    # Address information
    address = models.TextField(null=True, blank=True)
    country = CountryField(blank_label='(select country)', null=True, blank=True)

    # Dropbox file paths instead of FileField
    id_document = models.URLField(blank=True, null=True)
    selfie = models.URLField(blank=True, null=True)
    address_document = models.URLField(blank=True, null=True)

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected')
        ],
        default='pending'
    )
    rejection_reason = models.TextField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        get_user_model(),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_kyc_requests'
    )

    class Meta:
        get_latest_by = 'created_at'
        ordering = ['-created_at']

    def clean(self):
        """Validate KYC request data"""
        if self.status in ['approved', 'rejected'] and not self.reviewed_by:
            raise ValidationError('Reviewer is required for status change')

        # Check for pending requests
        pending_requests = KYCRequest.objects.filter(
            user=self.user,
            status='pending'
        ).exclude(pk=self.pk)

        if pending_requests.exists() and self.status == 'pending':
            raise ValidationError('User already has a pending KYC request')

    def save(self, *args, **kwargs):
        """Upload files to Dropbox before saving"""
        dropbox_service = DropboxService.get_instance()

        if isinstance(self.id_document, models.fields.files.FieldFile):
            dropbox_path = f"/kyc_documents/id/{self.user.id}_{self.id_document.name}"
            self.id_document = dropbox_service.upload_file(self.id_document, dropbox_path)

        if isinstance(self.selfie, models.fields.files.FieldFile):
            dropbox_path = f"/kyc_documents/selfie/{self.user.id}_{self.selfie.name}"
            self.selfie = dropbox_service.upload_file(self.selfie, dropbox_path)

        if isinstance(self.address_document, models.fields.files.FieldFile):
            dropbox_path = f"/kyc_documents/address/{self.user.id}_{self.address_document.name}"
            self.address_document = dropbox_service.upload_file(self.address_document, dropbox_path)

        super().save(*args, **kwargs)

    def get_private_url(self, file_field):
        """
        Get the secure private URL for a file using Dropbox.
        """
        dropbox_service = DropboxService()
        file_path = getattr(self, file_field)


        # Fetch the temporary link from Dropbox
        return dropbox_service.get_temporary_link(f"/{file_path}")

    @classmethod
    def create_from_profile(cls, user_profile, **additional_data):
        """
        Create a KYC request pre-filled with user profile data
    
        Args:
            user_profile: UserProfile instance
            additional_data: Any additional fields to override or add
        
        Returns:
            KYCRequest: New pre-filled KYC request instance
        """
        # Construct address from available fields
        address_parts = filter(None, [user_profile.city, user_profile.state, user_profile.country])
        address = ", ".join(address_parts)


        profile_data = {
            'user': user_profile,
            'full_name': user_profile.full_name,
            'date_of_birth': user_profile.date_of_birth,
            'country': user_profile.country,
            'address': address  # Add constructed address
        }

        # Override or add any additional data
        profile_data.update(additional_data)

        return cls.objects.create(**profile_data)
