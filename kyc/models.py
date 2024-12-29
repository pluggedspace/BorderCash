from time import timezone

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from dynaconf import ValidationError

from app.models import UserProfile
from django_countries.fields import CountryField

from kyc.services.validators import validate_document_size, validate_document_type


class KYCRequest(models.Model):
    # User relationship
    user = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='kyc_requests'
    )

    # Personal information
    full_name = models.CharField(max_length=255)
    date_of_birth = models.DateField(null=True, blank=True)

    # Address information
    address = models.TextField(null=True, blank=True)
    country = CountryField(blank_label='(select country)', null=True, blank=True)

    # Documents
    id_document = models.FileField(
        upload_to='kyc_documents/id/',
        validators=[validate_document_size, validate_document_type]
    )
    selfie = models.FileField(
        upload_to='kyc_documents/selfie/',
        validators=[validate_document_size, validate_document_type]
    )
    address_document = models.FileField(
        upload_to='kyc_documents/address/',
        validators=[validate_document_size, validate_document_type]
    )

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
        # Set reviewed_at when status changes
        if self.pk:
            old_instance = KYCRequest.objects.get(pk=self.pk)
            if old_instance.status != self.status:
                self.reviewed_at = timezone.now()

                # Create notification
                Notification.objects.create(
                    user=self.user,
                    message=self._get_status_change_message(),
                    notification_type='kyc_status'
                )

        super().save(*args, **kwargs)

    def _get_status_change_message(self):
        """Generate notification message for status change"""
        if self.status == 'approved':
            return "Your KYC verification has been approved!"
        elif self.status == 'rejected':
            reason = ": {self.rejection_reason}" if self.rejection_reason else ""
            return "Your KYC verification was rejected{reason}"
        return "Your KYC status has been updated to {self.status}"


class Notification(models.Model):
    user = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    message = models.TextField()
    notification_type = models.CharField(
        max_length=50,
        choices=[
            ('kyc_status', 'KYC Status Change'),
            ('reminder', 'Reminder'),
            ('other', 'Other')
        ],
        default='other'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def mark_as_read(self):
        from django.utils.timezone import now
        self.read_at = now()
        self.save()
