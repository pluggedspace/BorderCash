from django.db.models.signals import post_save
from django.dispatch import receiver
from transactions.models import Transaction
from .models import Dispute
from .notifications import send_notification
from .tasks import process_refund  # Import Celery refund task

@receiver(post_save, sender=Dispute)
def handle_dispute(sender, instance, created, **kwargs):
    """ Automatically process refunds & notify users on dispute status changes """
    
    if created:
        # Automatically process refund if applicable
        if instance.category in ["Failed Transaction", "Duplicate Charge"]:
            process_refund.delay(instance.id)

    # Notify user when status changes
    if instance.status in ["resolved", "escalated", "closed"]:
        send_notification(instance.user, f"Your dispute is now {instance.get_status_display()}.")

@receiver(post_save, sender=Transaction)
def create_dispute_on_failed_transaction(sender, instance, created, **kwargs):
    """ Auto-create a dispute when a transaction fails """
    if created and instance.status == 'failed':
        # Check if a dispute already exists for this transaction
        if not Dispute.objects.filter(transaction_id=instance.transaction_id, user=instance.user).exists():
            dispute = Dispute.objects.create(
                user=instance.user,
                transaction_id=instance.transaction_id,
                category="Failed Transaction",
                status="open",
            )
            send_notification(instance.user, "A dispute has been created for your failed transaction.")
