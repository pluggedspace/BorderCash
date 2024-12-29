from django.db.models import Sum
from django.core.mail import send_mail
from django.core.cache import cache
from decimal import Decimal
from datetime import datetime
import logging
from enum import Enum
from tenacity import retry, stop_after_attempt, wait_fixed
from sklearn.ensemble import IsolationForest
import numpy as np

from app.models import USDAccount, Transaction, ReconciliationHistory, PlatformAccount

logger = logging.getLogger(__name__)


# Enums for Reconciliation and Discrepancy Types
class ReconciliationType(Enum):
    INDIVIDUAL = "individual"
    SYSTEM = "system"


class DiscrepancyType(Enum):
    BALANCE_MISMATCH = "balance_mismatch"
    MISSING_TRANSACTION = "missing_transaction"


# Correction Suggestion and Analyzer
class CorrectionSuggestion:
    def __init__(self, discrepancy_type, description, correction_steps, confidence, impact):
        self.discrepancy_type = discrepancy_type
        self.description = description
        self.correction_steps = correction_steps
        self.confidence = confidence
        self.impact = impact

    def to_dict(self):
        return {
            'discrepancy_type': self.discrepancy_type.value,
            'description': self.description,
            'correction_steps': self.correction_steps,
            'confidence': round(self.confidence, 2),
            'impact': str(self.impact),
        }


class CorrectionAnalyzer:
    def __init__(self):
        self.common_patterns = {
            'rounding': Decimal('0.01'),
        }

    def analyze_discrepancy(self, difference):
        suggestions = []
        if abs(difference) < self.common_patterns['rounding']:
            suggestions.append(CorrectionSuggestion(
                DiscrepancyType.BALANCE_MISMATCH,
                "Rounding difference detected.",
                ["Review system rounding logic.", "Apply correction."],
                0.95,
                difference,
            ))
        return suggestions


# Reconciliation Service
class ReconciliationService:
    CACHE_KEY_TOTAL_BALANCE = 'total_ledger_balance'

    def __init__(self):
        self.analyzer = CorrectionAnalyzer()

    @staticmethod
    def get_total_ledger_balance(use_cache=True):
        """Calculate total ledger balance with optional caching."""
        if use_cache:
            cached_balance = cache.get(ReconciliationService.CACHE_KEY_TOTAL_BALANCE)
            if cached_balance:
                return Decimal(cached_balance)

        total_balance = USDAccount.objects.aggregate(Sum('balance'))['balance__sum'] or Decimal('0.00')
        cache.set(ReconciliationService.CACHE_KEY_TOTAL_BALANCE, str(total_balance), timeout=3600)
        return total_balance

    @staticmethod
    def get_actual_pooled_balance():
        """Fetch actual pooled account balance from PlatformAccount."""
        try:
            pooled_account = PlatformAccount.objects.get(name="Pool")
            return pooled_account.balance
        except PlatformAccount.DoesNotExist:
            logger.error("Pooled account not found.")
            return Decimal('0.00')

    def reconcile(self, tolerance=Decimal('0.01')):
        """Perform reconciliation with anomaly detection."""
        total_ledger_balance = self.get_total_ledger_balance()
        actual_pooled_balance = self.get_actual_pooled_balance()
        difference = abs(total_ledger_balance - actual_pooled_balance)

        if difference > tolerance:
            discrepancies = self.analyzer.analyze_discrepancy(difference)
            self._handle_discrepancy(total_ledger_balance, actual_pooled_balance, discrepancies)
            self._record_history(total_ledger_balance, actual_pooled_balance, difference, status="Discrepancy")
            return False

        logger.info("Reconciliation successful.")
        self._record_history(total_ledger_balance, actual_pooled_balance, Decimal('0.00'), status="Success")
        return True

    @staticmethod
    def _handle_discrepancy(ledger_balance, actual_balance, discrepancies):
        error_message = (f"Discrepancy detected:\n"
                         f"Ledger: ${ledger_balance}, Pooled: ${actual_balance}\n"
                         f"Suggestions: {[d.to_dict() for d in discrepancies]}")
        logger.error(error_message)
        send_mail(
            subject="URGENT: Account Reconciliation Discrepancy",
            message=error_message,
            from_email="system@yourcompany.com",
            recipient_list=["finance@yourcompany.com"],
            fail_silently=False,
        )

    @staticmethod
    def _record_history(ledger_balance, pooled_balance, discrepancy, status):
        """Record reconciliation history."""
        ReconciliationHistory.objects.create(
            timestamp=datetime.now(),
            ledger_balance=ledger_balance,
            pooled_balance=pooled_balance,
            discrepancy=discrepancy,
            status=status
        )


# System-wide Reconciliation
class TransactionReconciler:
    @staticmethod
    def reconcile_system():
        """Perform system-wide reconciliation."""
        all_accounts = USDAccount.objects.all()
        total_ledger = sum(account.balance for account in all_accounts)
        total_transactions = sum(Transaction.objects.filter(account=account).count() for account in all_accounts)

        logger.info(f"System Reconciliation Complete. Ledger: ${total_ledger}, "
                    f"Total Transactions: {total_transactions}")

    @staticmethod
    def detect_anomalies(transaction_amounts):
        """Detect anomalies in transaction data using machine learning."""
        model = IsolationForest(random_state=42)
        transaction_array = np.array(transaction_amounts).reshape(-1, 1)
        anomalies = model.fit_predict(transaction_array)
        return [amount for amount, anomaly in zip(transaction_amounts, anomalies) if anomaly == -1]


# Usage
def run_reconciliation():
    reconciliation_service = ReconciliationService()
    system_reconciler = TransactionReconciler()

    # Run individual and system reconciliations
    if not reconciliation_service.reconcile():
        system_reconciler.reconcile_system()

