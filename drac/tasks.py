from celery import shared_task
import logging
from django.utils import timezone
from decimal import Decimal
from django.core.exceptions import ObjectDoesNotExist

from .models import Anomaly, ComplianceCheck, AuditLog, Reconciliation
from app.models import Transaction, User
from kyc.models import KYCRequest
from .services import detect_anomalies, perform_compliance_check, log_audit, ReconciliationService


logger = logging.getLogger(__name__)

# ----------------------------
# Anomaly Detection Task
# ----------------------------
@shared_task
def detect_anomaly_task(transaction_id):
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        recent_transactions = list(Transaction.objects.filter(
            user=transaction.user
        ).order_by('-timestamp')[:50])

        if not recent_transactions:
            logger.warning(f"No recent transactions found for user {transaction.user}.")
            return

        detect_anomalies(recent_transactions)  # Pass transactions directly
        
        logger.info(f"Anomaly detection completed for transaction {transaction.id}.")
        
    except ObjectDoesNotExist as e:
        logger.error(f"Transaction not found: {e}")
    except Exception as e:
        logger.error(f"Error detecting anomaly for transaction {transaction_id}: {e}")

# ----------------------------
# Compliance Check Task
# ----------------------------
@shared_task
def run_compliance_check_task(user_id):
    try:
        user_profile = UserProfile.objects.get(user_id=user_id)
        result = perform_compliance_check(user_profile.user)  # Use user_profile.user
        
        if result:
            logger.info(f"Compliance check completed for user {user_profile.user.username} - Result: {result}")
        else:
            logger.warning(f"Compliance check could not be performed for user {user_profile.user.username}.")
            
    except ObjectDoesNotExist as e:
        logger.error(f"UserProfile not found for compliance check: {e}")
    except Exception as e:
        logger.error(f"Error running compliance check for user_id {user_id}: {e}")

# ----------------------------
# Audit Task
# ----------------------------
@shared_task
def run_audit_task(transaction_id):
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        description = f"Audit performed for transaction {transaction.id}"
        
        log_audit(transaction, description)  # Call the service function
        
        logger.info(f"Audit logged for transaction {transaction.id}.")
        
    except ObjectDoesNotExist as e:
        logger.error(f"Transaction not found for audit: {e}")
    except Exception as e:
        logger.error(f"Error running audit for transaction {transaction_id}: {e}")


# ----------------------------
# Transaction Reconciliation Task
# ----------------------------
@shared_task(bind=True, max_retries=3)
def reconcile_transaction_task(self, transaction_identifier, expected_amount):
    """
    Enhanced task that handles:
    - UUID primary keys (id)
    - String transaction_ids
    - Automatic retries
    """
    try:
        success, result = ReconciliationService.reconcile_single_transaction(
            transaction_identifier=transaction_identifier,
            expected_amount=expected_amount
        )
        
        if not success:
            if "not found" not in result.get('error', '').lower():
                logger.warning(f"Retrying... Attempt {self.request.retries}")
                raise self.retry(exc=Exception(result.get('error')))
        
        return result

    except Exception as e:
        logger.error(f"Permanent reconciliation failure: {str(e)}")
        return {
            "error": str(e),
            "identifier": str(transaction_identifier),
            "expected_amount": str(expected_amount)
        }

@shared_task
def full_reconciliation_task():
    """Task for full system reconciliation"""
    try:
        success, result = ReconciliationService.full_system_reconciliation()
        
        if not success:
            if 'discrepancy' in result:
                logger.warning(f"System discrepancy found: {result['discrepancy']}")
            else:
                logger.error(f"System reconciliation error: {result.get('error')}")
        
        return result

    except Exception as e:
        logger.critical(f"System reconciliation failed: {str(e)}")
        return {"error": str(e)}

# ----------------------------
# Scheduled Reconciliation Task
# ----------------------------
@shared_task
def scheduled_reconciliation_task():
    try:
        logger.info(f"Running scheduled reconciliation at {timezone.now()}")
        success = reconcile_transactions()  # Call the service function
        
        if success:
            logger.info("Scheduled reconciliation completed successfully.")
        else:
            logger.error("Discrepancy detected during scheduled reconciliation.")
            
    except Exception as e:
        logger.error(f"Error during scheduled reconciliation: {e}")

