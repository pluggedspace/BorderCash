from django.db.models import Sum
from django.core.mail import send_mail
from django.core.cache import cache
from decimal import Decimal
from datetime import datetime
import logging
from enum import Enum
from sklearn.ensemble import IsolationForest
import numpy as np
from uuid import UUID
from decimal import Decimal, InvalidOperation
from app.models import PlatformAccount, Transaction, UserProfile 
from drac.models import Anomaly, AuditLog, Reconciliation, ComplianceCheck
from kyc.models import KYCRequest

from django.db.models import Sum

logger = logging.getLogger(__name__)

# Enums for Reconciliation and Discrepancy Types
class ReconciliationType(Enum):
    INDIVIDUAL = "individual"
    SYSTEM = "system"

class DiscrepancyType(Enum):
    BALANCE_MISMATCH = "balance_mismatch"
    MISSING_TRANSACTION = "missing_transaction"

# Anomaly Detection
def detect_anomalies(transactions):
    if not transactions:
        return []

    model = IsolationForest(random_state=42)
    transaction_amounts = [transaction.amount for transaction in transactions]
    transaction_array = np.array(transaction_amounts).reshape(-1, 1)
    anomalies = model.fit_predict(transaction_array)
    
    anomalous_transactions = [
        transaction for transaction, anomaly in zip(transactions, anomalies) if anomaly == -1
    ]

    for transaction in anomalous_transactions:
        Anomaly.objects.create(
            transaction=transaction,
            description=f"Detected anomaly with amount: {transaction.amount}",
            status="Pending"
        )
        logger.warning(f"Anomaly detected for transaction {transaction.id} - Amount: {transaction.amount}")

    return anomalous_transactions


# Audit Logging
def log_audit(transaction, description):
    AuditLog.objects.create(
        transaction=transaction,
        description=description,
        status="Completed"
    )
    logger.info(f"Audit logged for transaction {transaction.id}")

# Compliance Check
def perform_compliance_check(user, kyc_request):
    if not kyc_request:
        logger.warning(f"No KYC record found for user {user.id}")
        return "KYC record not found."
    
    # Convert User to UserProfile instance
    try:
        user_profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        logger.error(f"UserProfile not found for user {user.id}")
        return "UserProfile not found."

    compliance_status = "Approved" if kyc_request.status else "Failed"

    ComplianceCheck.objects.create(
        user=user_profile,  # Use the UserProfile instance here
        kyc=kyc_request,
        result=compliance_status
    )

    logger.info(f"Compliance check for user {user.id} - Status: {compliance_status}")

# Reconciliation
class ReconciliationService:
    @staticmethod
    def validate_transaction_id(transaction_id):
        """Flexible transaction ID validation"""
        try:
            # Try UUID first (if some IDs are UUIDs)
            try:
                return UUID(str(transaction_id))
            except ValueError:
                pass
            
            # Try integer (for auto-increment IDs)
            try:
                return int(transaction_id)
            except ValueError:
                pass
            
            # Accept string IDs as-is
            if isinstance(transaction_id, str) and transaction_id.strip():
                return transaction_id.strip()
            
            raise ValueError("Invalid transaction ID format")
            
        except Exception as e:
            logger.error(f"Invalid transaction ID: {transaction_id}. Error: {str(e)}")
            raise ValueError(f"Invalid transaction ID: {transaction_id}")


    @staticmethod
    def validate_amount(amount):
        """Validate amount is a proper decimal"""
        try:
            return Decimal(str(amount))
        except (InvalidOperation, TypeError, ValueError) as e:
            logger.error(f"Invalid amount: {amount}. Error: {str(e)}")
            raise ValueError(f"Invalid amount format: {amount}")
            
    @staticmethod
    def validate_transaction_identifier(transaction_identifier):
        """Handles both UUID (primary key) and transaction_id (string)"""
        try:
            # Try as UUID (primary key)
            try:
                return {'field': 'id', 'value': UUID(str(transaction_identifier))}
            except ValueError:
                pass
            
            # Try as transaction_id (string reference)
            if isinstance(transaction_identifier, str) and transaction_identifier.strip():
                return {'field': 'transaction_id', 'value': transaction_identifier.strip()}
            
            raise ValueError("Invalid transaction identifier format")
        except Exception as e:
            logger.error(f"Invalid transaction identifier: {transaction_identifier}. Error: {str(e)}")
            raise


    @staticmethod
    def reconcile_single_transaction(transaction_identifier, expected_amount):
        """Enhanced to handle both ID types"""
        try:
            # Validate inputs
            id_info = ReconciliationService.validate_transaction_identifier(transaction_identifier)
            expected_amount = Decimal(str(expected_amount))

            # Get transaction using either field
            transaction = Transaction.objects.get(**{id_info['field']: id_info['value']})
            
            actual_amount = transaction.amount
            status = "Matched" if abs(actual_amount - expected_amount) <= Decimal('0.01') else "Mismatched"
            
            Reconciliation.objects.create(
                transaction=transaction,
                expected_amount=expected_amount,
                actual_amount=actual_amount,
                status=status
            )
            
            return True, {
                "identifier_type": id_info['field'],
                "transaction_id": str(transaction.id),
                "external_reference": transaction.transaction_id,
                "status": status,
                "amounts": {
                    "expected": str(expected_amount),
                    "actual": str(actual_amount)
                }
            }

        except Transaction.DoesNotExist:
            error_msg = f"Transaction not found: {transaction_identifier} ({id_info['field']})"
            logger.error(error_msg)
            return False, {"error": error_msg}
        except Exception as e:
            logger.error(f"Reconciliation failed: {str(e)}")
            return False, {"error": str(e)}            


    @staticmethod
    def full_system_reconciliation(tolerance=Decimal('0.01')):
        """Enhanced system-wide reconciliation"""
        try:
            logger.info("Starting full system reconciliation...")
            
            # Get balances
            total_transactions = Transaction.objects.aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
            
            vault = PlatformAccount.objects.filter(name="Vault").first()
            if not vault:
                raise ValueError("Vault account not found")

            # Compare balances
            discrepancy = abs(total_transactions - vault.balance)
            status = "Balanced" if discrepancy <= tolerance else "Discrepancy"
            
            # Create reconciliation record
            Reconciliation.objects.create(
                transaction=None,
                expected_amount=total_transactions,
                actual_amount=vault.balance,
                status=status,
                system_reconciliation=True
            )
            
            if status == "Discrepancy":
                logger.warning(f"System discrepancy detected: {discrepancy}")
                return False, {"discrepancy": str(discrepancy)}
            
            logger.info("System reconciliation successful")
            return True, {"status": "Balanced"}

        except Exception as e:
            logger.error(f"System reconciliation failed: {str(e)}")
            return False, {"error": str(e)}
            
# Handle Discrepancies
def handle_discrepancy(reconciliation, discrepancies):
    description = (
        f"Reconciliation ID: {reconciliation.id}\n"
        f"Discrepancies: {', '.join(map(str, discrepancies))}\n"
    )
    
    send_mail(
        subject="Discrepancy Detected in Reconciliation",
        message=description,
        from_email="system@mail.swifwallet.com",
        recipient_list=["admin@swifwallet.com"],
        fail_silently=False,
    )
    logger.error(f"Discrepancy reported for reconciliation {reconciliation.id}")


 