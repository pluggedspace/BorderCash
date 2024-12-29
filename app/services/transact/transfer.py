from decimal import Decimal, InvalidOperation
import logging
import uuid
import transaction
from django.db import transaction
from django.contrib.auth import get_user_model
from app.models import USDAccount, Transaction, PlatformAccount, Fee
from app.services.transact.utils.utils import has_sufficient_balance, InsufficientFundsError, calculate_fee

logger = logging.getLogger(__name__)

class TransferService:
    def process_internal_transfer(self, sender, recipient, amount):
        # Ensure amount is a Decimal
        try:
            amount = Decimal(str(amount))
        except (InvalidOperation, TypeError):
            raise ValueError('Invalid transfer amount')

        if amount <= 0:
            raise ValueError('Transfer amount must be greater than zero')

        # Step 1: Calculate fees using the Fee model
        try:
            total_amount, fee_amount, net_amount = calculate_fee('transfer', amount)
        except ValueError as e:
            logger.error(f"Fee calculation error: {e}")
            raise

        # Generate a unique transaction ID for this transfer
        internal_transaction_id = {'id': str(uuid.uuid4())}

        try:
            with transaction.atomic():
                User = get_user_model()
                sender_account = USDAccount.objects.select_for_update().get(user=sender)
                recipient_account = USDAccount.objects.select_for_update().get(user=recipient)

                # Ensure all amount calculations use Decimal
                if not has_sufficient_balance(sender_account, total_amount):
                    raise InsufficientFundsError("Insufficient funds")

                # Step 2: Proceed with the transfer
                sender_account.withdraw(Decimal(amount))
                recipient_account.deposit(Decimal(net_amount))

                # Step 3: Fetch the platform account for commissions
                platform_account = PlatformAccount.objects.get(name='Fees')
                platform_account.deposit(Decimal(fee_amount))

                # Step 4: Create transaction records for both sender, recipient, and the fee
                self._create_transaction(sender, 'transfer', amount, f"Transfer to {recipient.username}",
                                         internal_transaction_id)
                self._create_transaction(recipient, 'transfer', net_amount, f"Transfer from {sender.username}",
                                         internal_transaction_id)
                self._create_transaction(sender, 'fee', fee_amount, "Transfer fee", internal_transaction_id)
            
            logger.info(f"Transfer successful from {sender.username} to {recipient.username}")
            return {'status': 'success'}
        
        except InsufficientFundsError as e:
            logger.error(f"Insufficient funds for {sender.username}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error during transfer: {e}")
            raise

    @staticmethod
    def _create_transaction(user, transaction_type, amount, description, internal_transaction_id):
        # Ensure amount is converted to Decimal
        amount = Decimal(str(amount))
        
        # Create transaction entry with internal transaction ID
        Transaction.objects.create(
            user=user,
            amount=amount,
            transaction_type=transaction_type,
            status='completed',
            description=description,
            transaction_id=internal_transaction_id.get('id')  # Use the same ID for both transactions
        )



