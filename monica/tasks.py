from celery import shared_task
from django.contrib.auth import get_user_model
from .utils import check_low_balance, check_pending_transactions, send_alert
from .models import Dispute, RefundLog
from datetime import datetime, timedelta
from django.core.mail import send_mail
from django.utils.timezone import now

from app.models import Transaction
from .notifications import send_notification
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

@shared_task
def monitor_user_accounts():
    users = User.objects.all()
    for user in users:
        low_balance_alert = check_low_balance(user)
        if low_balance_alert:
            send_alert(user, low_balance_alert)

        pending_tx_alert = check_pending_transactions(user)
        if pending_tx_alert:
            send_alert(user, pending_tx_alert)

@shared_task
def process_refund(dispute_id):
    """ Asynchronously processes a refund and updates dispute status """
    try:
        dispute = Dispute.objects.get(id=dispute_id)

        # Prevent duplicate processing
        if dispute.refund_status in ["completed", "failed"]:
            return  # Refund already processed

        transaction = Transaction.objects.filter(transaction_id=dispute.transaction_id, user=dispute.user).first()

        if transaction.can_be_refunded():  # Ensure transaction is refundable
            transaction.refund()  # Perform refund operation
            dispute.refund_status = 'completed'
            dispute.status = 'resolved'
            dispute.save()

            # Notify user
            send_notification(dispute.user, "Your refund has been processed successfully.")

        else:
            dispute.refund_status = 'failed'
            dispute.status = 'escalated'
            dispute.save()
            send_notification(dispute.user, "Your dispute has been escalated for manual review.")

    except (Dispute.DoesNotExist, Transaction.DoesNotExist):
        pass  # Handle missing dispute or transaction gracefully

@shared_task
def notify_support_about_escalated_disputes():
    """Notify support team about escalated disputes"""
    escalated_disputes = Dispute.objects.filter(status="escalated")
    
    if escalated_disputes.exists():
        message = "New escalated disputes need attention:\n"
        for dispute in escalated_disputes:
            message += f"{dispute.user.email} - {dispute.category} (ID: {dispute.id})\n"

        send_mail(
            subject="Escalated Disputes Alert",
            message=message,
            from_email="mail@border.cash",
            recipient_list=["support@border.cash"],
        )
        logger.info("Escalated dispute notification sent to support.")

