from django.db.models.signals import post_save
from django.dispatch import receiver
from kyc.models import KYCRequest
from kyc.tasks import send_notification_task


@receiver(post_save, sender=KYCRequest)
def handle_kyc_status_change(sender, instance, created, **kwargs):
    # Only trigger if the status has changed
    if not created:
        old_instance = KYCRequest.objects.get(pk=instance.pk)
        if old_instance.status != instance.status:
            message = instance._get_status_change_message()
            # Trigger Celery task
            send_notification_task.delay(instance.user.id, message)
