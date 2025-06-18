from django.db.models.signals import post_save
from django.dispatch import receiver
from app.models import Transaction
from kyc.models import KYCRequest
from .tasks import detect_anomaly_task, run_compliance_check_task, run_audit_task, reconcile_transaction_task

@receiver(post_save, sender=Transaction)
def transaction_handler(sender, instance, created, **kwargs):
    """
    Triggered when a new Transaction is created.
    Initiates anomaly detection, audit logging, and transaction reconciliation.
    """
    if created:
        # Trigger anomaly detection
        detect_anomaly_task.delay(instance.id)
        
        # Trigger audit logging
        run_audit_task.delay(instance.id)
        
        # Trigger transaction reconciliation
        reconcile_transaction_task.delay(instance.id, expected_amount=str(instance.amount))  # Convert to string for Celery compatibility


@receiver(post_save, sender=KYCRequest)
def kyc_handler(sender, instance, created, **kwargs):
    """
    Triggered when a new KYCRequest is created.
    Initiates compliance check process.
    """
    if created:
        run_compliance_check_task.delay(instance.user.id)  # Only pass user.id for compatibility
