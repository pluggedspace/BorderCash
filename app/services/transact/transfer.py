from decimal import Decimal, InvalidOperation
import logging
import uuid
import transaction
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from app.models import USDAccount, Transaction, PlatformAccount, Fee
from app.services.transact.utils.utils import has_sufficient_balance, InsufficientFundsError, calculate_fee

logger = logging.getLogger(__name__)

class TransferService:
    def process_internal_transfer(self, sender, recipient, amount):
        try:
            amount = Decimal(str(amount))
        except (InvalidOperation, TypeError):
            raise ValueError('Invalid transfer amount')

        if amount <= 0:
            raise ValueError('Transfer amount must be greater than zero')

        try:
            total_amount, fee_amount, net_amount = calculate_fee('transfer', amount)
        except ValueError as e:
            logger.error(f"Fee calculation error: {e}")
            raise

        internal_transaction_id = {'id': str(uuid.uuid4())}
        timestamp = timezone.now()

        try:
            with transaction.atomic():
                sender_account = USDAccount.objects.select_for_update().get(user=sender)
                recipient_account = USDAccount.objects.select_for_update().get(user=recipient)

                if not has_sufficient_balance(sender_account, total_amount):
                    raise InsufficientFundsError("Insufficient funds")

                sender_account.withdraw(Decimal(amount))
                recipient_account.deposit(Decimal(net_amount))

                platform_account = PlatformAccount.objects.get(name='Commission')
                platform_account.deposit(Decimal(fee_amount))

                # Create transaction records with unique memos
                self.create_transaction(
                    user=sender,
                    transaction_type='transfer',
                    amount=amount,
                    description=f"Transfer to {recipient.username}",
                    internal_transaction_id=internal_transaction_id,
                    memo=f"SEND-{internal_transaction_id['id'][:8]}-{timestamp.strftime('%Y%m%d%H%M%S')}"
                )
                
                self.create_transaction(
                    user=recipient,
                    transaction_type='transfer',
                    amount=net_amount,
                    description=f"Transfer from {sender.username}",
                    internal_transaction_id=internal_transaction_id,
                    memo=f"RECV-{internal_transaction_id['id'][:8]}-{timestamp.strftime('%Y%m%d%H%M%S')}"
                )
                
                self.create_transaction(
                    user=sender,
                    transaction_type='transfer',
                    amount=fee_amount,
                    description=f"Transfer to {recipient.username}",
                    internal_transaction_id=internal_transaction_id,
                    memo=f"FEE-{internal_transaction_id['id'][:8]}-{timestamp.strftime('%Y%m%d%H%M%S')}"
                )
            
            logger.info(f"Transfer successful from {sender.username} to {recipient.username}")
            return {'status': 'success'}
        
        except InsufficientFundsError as e:
            logger.error(f"Insufficient funds for {sender.username}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error during transfer: {e}")
            raise

    @classmethod
    def create_transaction(cls, user, transaction_type, amount, description, internal_transaction_id, memo=None):
        try:
            amount = Decimal(str(amount))
            transaction_id = internal_transaction_id.get('id')
            
            if not transaction_id:
                raise ValueError("Invalid internal_transaction_id: 'id' is missing.")
            
            if memo is None:
                memo = f"{transaction_type.upper()}-{transaction_id[:8]}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
            
            # Create the transaction record with the memo field
            Transaction.objects.create(
                user=user,
                amount=amount,
                transaction_type=transaction_type,
                status='completed',
                description=description,
                transaction_id=transaction_id,
                details=f"Transaction initiated by: {user.username}",
                memo=memo,  # Add unique memo
                timestamp=timezone.now(),
                currency='USD'  # Assuming USD is the default currency
            )
        except Exception as e:
            logger.error(f"Error creating transaction for {user.username}: {e}")
            raise ValueError(f"Failed to create transaction: {e}")