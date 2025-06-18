from django.db.models.signals import post_save
from django.dispatch import receiver
from kyc.models import KYCRequest
from kyc.tasks import send_notification_task
from app.utils.mail import send_email  

@receiver(post_save, sender=KYCRequest)
def handle_kyc_status_change(sender, instance, created, **kwargs):
    """Handle KYC status updates by sending notifications and emails."""
    
    if created:
        return  # Do nothing if this is a new KYC request

    try:
        old_instance = KYCRequest.objects.get(pk=instance.pk)
    except KYCRequest.DoesNotExist:
        return  # Edge case where the instance doesn't exist

    # Check if status has changed
    if old_instance.status != instance.status:
        message = instance._get_status_change_message()
        
        # Send a push notification
        send_notification_task.delay(instance.user.id, message)

        # If KYC is approved or rejected, send an email using ZeptoMail
        if instance.status.lower() in ["approved", "rejected"]:
            subject = "KYC Verification Update"
            context = {
                "first_name": instance.user.first_name,
                "status": instance.status.lower(),
                "description": instance.description or "Please log in to your account for more details."
            }

            send_email.delay(  # Using Celery to send asynchronously
                subject=subject,
                recipient=instance.user.email,
                template_name="kyc_status_update",  # Must match your template filename (without .html)
                context=context
            )
