from datetime import timedelta
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.db.models import Sum
from app.models import Transaction, Alert, HighRiskCountry


class TransactionMonitor:
    def __init__(self, transaction):
        self.transaction = transaction

    def is_large_transaction(self):
        """Check if the transaction amount is greater than $10,000."""
        return self.transaction.amount > 10000

    def is_high_frequency(self):
        """Check if there are more than 5 transactions in the last 10 minutes."""
        recent_transaction_count = Transaction.objects.filter(
            user=self.transaction.user,
            timestamp__gte=timezone.now() - timedelta(minutes=10)
        ).count()
        return recent_transaction_count > 5

    def is_high_risk_country(self):
        """Check if the transaction is from a high-risk country."""
        high_risk_countries = HighRiskCountry.objects.values_list('name', flat=True)
        return self.transaction.geolocation in high_risk_countries

    def is_unusual_pattern(self):
        """Check if the transaction amount is more than 2.5 times the user's average transaction."""
        average_amount = self.transaction.user.get_average_transaction_amount()
        return self.transaction.amount > average_amount * 2.5

    def is_round_number_transaction(self):
        """Check if the transaction amount is a round number."""
        return self.transaction.amount % 1000 == 0

    def is_geolocation_mismatch(self):
        """Check if the transaction location differs from the user's last known location."""
        user_previous_location = self.transaction.user.last_known_location
        return self.transaction.geolocation != user_previous_location

    def is_linked_account_activity(self):
        """Check if there are more than 3 transactions linked to the same beneficiary."""
        linked_transactions = Transaction.objects.filter(
            user=self.transaction.user,
            beneficiary=self.transaction.beneficiary
        ).count()
        return linked_transactions > 3

    def is_rapid_fund_movement(self):
        """Check if the user is sending and receiving funds quickly (more than 3 in/out transactions within an hour)."""
        incoming = Transaction.objects.filter(
            user=self.transaction.user,
            type="IN",
            timestamp__gte=timezone.now() - timedelta(hours=1)
        ).count()
        outgoing = Transaction.objects.filter(
            user=self.transaction.user,
            type="OUT",
            timestamp__gte=timezone.now() - timedelta(hours=1)
        ).count()
        return incoming > 3 and outgoing > 3

    def is_transaction_splitting(self):
        """Check if the user is splitting transactions to avoid detection (total transactions in the last 24 hours > $10,000)."""
        recent_transactions = Transaction.objects.filter(
            user=self.transaction.user,
            timestamp__gte=timezone.now() - timedelta(days=1)
        ).aggregate(total_amount=Sum('amount'))
        return recent_transactions['total_amount'] > 10000

    def is_high_risk_merchant(self):
        """Check if the transaction is with a high-risk merchant category."""
        high_risk_categories = ['Gambling', 'Crypto Exchange', 'Pawn Shop']
        return self.transaction.merchant_category in high_risk_categories

    def is_unverified_account(self):
        """Check if the user account is unverified."""
        return not self.transaction.user.is_verified

    def is_frequent_cash_withdrawal(self):
        """Check if the user has made more than 5 withdrawals in the last 7 days."""
        recent_withdrawals = Transaction.objects.filter(
            user=self.transaction.user,
            type="WITHDRAWAL",
            timestamp__gte=timezone.now() - timedelta(days=7)
        ).count()
        return recent_withdrawals > 5

    def is_blacklisted_account_or_country(self):
        """Check if the user's account or transaction country is blacklisted."""
        blacklisted_entities = ['Entity1', 'Entity2']
        blacklisted_countries = HighRiskCountry.objects.filter(is_blacklisted=True).values_list('name', flat=True)
        return self.transaction.user.name in blacklisted_entities or \
            self.transaction.geolocation in blacklisted_countries

    def get_rule_weights(self):
        """Assign weights to each rule for flagging transactions."""
        return {
            "Large transaction": 3,  # High weight due to risk
            "High frequency of transactions": 2,
            "Transaction from high-risk country": 2,
            "Unusual transaction pattern": 2,
            "Round-number transaction": 1,
            "Geolocation mismatch": 3,
            "Linked account activity": 2,
            "Rapid fund movement": 3,
            "Transaction splitting": 2,
            "High-risk merchant category": 3,
            "Unverified account": 1,
            "Frequent cash withdrawals": 2,
            "Blacklisted account or country": 4  # Highest weight due to high risk
        }

    def run_rules(self):
        """Evaluate each rule and calculate the total weight."""
        rules = {
            "Large transaction": self.is_large_transaction(),
            "High frequency of transactions": self.is_high_frequency(),
            "Transaction from high-risk country": self.is_high_risk_country(),
            "Unusual transaction pattern": self.is_unusual_pattern(),
            "Round-number transaction": self.is_round_number_transaction(),
            "Geolocation mismatch": self.is_geolocation_mismatch(),
            "Linked account activity": self.is_linked_account_activity(),
            "Rapid fund movement": self.is_rapid_fund_movement(),
            "Transaction splitting": self.is_transaction_splitting(),
            "High-risk merchant category": self.is_high_risk_merchant(),
            "Unverified account": self.is_unverified_account(),
            "Frequent cash withdrawals": self.is_frequent_cash_withdrawal(),
            "Blacklisted account or country": self.is_blacklisted_account_or_country(),
        }

        triggered_flags = []
        total_weight = 0

        # Check which rules triggered and calculate total weight
        for rule, triggered in rules.items():
            if triggered:
                triggered_flags.append(rule)
                total_weight += self.get_rule_weights().get(rule, 0)

        return triggered_flags, total_weight


def monitor_transaction(transaction):
    """Monitor the transaction and alert the admin if necessary."""
    monitor = TransactionMonitor(transaction)
    flags, total_weight = monitor.run_rules()

    # Define a threshold for total weight, which would be used to flag suspicious transactions
    if total_weight >= 10:
        Alert.objects.create(transaction=transaction, flags=flags)
        notify_admin(transaction, flags)


def notify_admin(transaction, flags):
    """Notify the admin if a suspicious transaction is detected."""
    send_mail(
        'Suspicious Transaction Alert',
        f"Transaction {transaction.id} flagged: {', '.join(flags)}",
        'admin@example.com',
        ['admin@example.com']
    )


@receiver(post_save, sender=Transaction)
def monitor_transaction_signal(sender, instance, **kwargs):
    """Automatically monitor transactions upon saving."""
    monitor_transaction(instance)
