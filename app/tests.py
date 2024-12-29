import unittest
from unittest.mock import patch, MagicMock
from decimal import Decimal

from app.services.transact.withdraw_crypto.withdraw import WithdrawalService
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swif.settings')
import django
django.setup()



class TestWithdrawalService(unittest.TestCase):

    def setUp(self):
        # Common setup for each test
        self.user = MagicMock(id=1)  # Mock user object with ID
        self.amount = Decimal("100.00")
        self.method = "crypto"
        self.recipient_address = "stellar_test_address"
        self.withdrawal_service = WithdrawalService(
            user=self.user,
            amount=self.amount,
            method=self.method,
            recipient_address=self.recipient_address
        )

    @patch('app.models.USDAccount.objects.get')
    def test_validate_balance_sufficient_funds(self, mock_get):
        # Setup mock to return a wallet with sufficient balance
        wallet = MagicMock(balance=Decimal("150.00"))
        mock_get.return_value = wallet
        validated_wallet = self.withdrawal_service.validate_balance()
        self.assertEqual(validated_wallet, wallet)

    @patch('app.models.USDAccount.objects.get')
    def test_validate_balance_insufficient_funds(self, mock_get):
        # Setup mock to return a wallet with insufficient balance
        wallet = MagicMock(balance=Decimal("50.00"))
        mock_get.return_value = wallet
        with self.assertRaises(InsufficientFundsError):
            self.withdrawal_service.validate_balance()

    @patch('app.models.Transaction.objects.create')
    def test_create_transaction_success(self, mock_create):
        # Test transaction creation with mock
        mock_create.return_value = MagicMock(id=1, status="pending")
        transaction = self.withdrawal_service.create_transaction(status="pending")
        self.assertEqual(transaction.status, "pending")
        mock_create.assert_called_once()

    @patch('app.models.USDAccount.objects.get')
    @patch('app.models.USDAccount.save')
    def test_update_user_balance(self, mock_save, mock_get):
        # Setup mock wallet with initial balance
        wallet = MagicMock(balance=Decimal("150.00"))
        mock_get.return_value = wallet
        self.withdrawal_service.update_user_balance(wallet)
        self.assertEqual(wallet.balance, Decimal("50.00"))
        mock_save.assert_called_once()

    @patch('app.services.transact.withdraw_crypto.withdraw_usdc.get_user_virtual_balance')
    @patch('app.services.transact.withdraw_crypto.withdraw_usdc.is_stellar_address')
    @patch('app.services.transact.withdraw_crypto.withdraw_usdc.process_stellar_withdrawal')
    def test_withdraw_usdc_successful(self, mock_stellar_withdrawal, mock_is_stellar, mock_balance):
        mock_balance.return_value = Decimal("150.00")  # Sufficient balance
        mock_is_stellar.return_value = True
        mock_stellar_withdrawal.return_value = {"status": "success", "transaction_id": "tx_123"}
        result = self.withdrawal_service.withdraw_usdc()
        self.assertEqual(result["status"], "success")

    @patch('app.services.transact.withdraw_crypto.withdraw_usdc.get_user_virtual_balance')
    def test_withdraw_usdc_insufficient_balance(self, mock_balance):
        # Set up insufficient balance
        mock_balance.return_value = Decimal("50.00")
        with self.assertRaises(InsufficientFundsError):
            self.withdrawal_service.withdraw_usdc()

    @patch('app.services.transact.withdraw_crypto.withdraw_crypto.process_transaction')
    @patch('app.services.transact.withdraw_crypto.utils.utils.calculate_fee')
    @patch('app.services.transact.withdraw_crypto.withdraw_crypto.is_valid_address')
    @patch('app.services.transact.withdraw_crypto.withdraw_crypto.get_user_virtual_balance')
    def test_withdraw_crypto_successful(self, mock_balance, mock_is_valid_address, mock_calculate_fee, mock_process_transaction):
        # Setup mocks for a successful withdrawal process
        mock_balance.return_value = Decimal("150.00")
        mock_is_valid_address.return_value = True
        mock_calculate_fee.return_value = Decimal("2.00")
        mock_process_transaction.return_value = MagicMock(transaction_hash="tx_456")

        result = self.withdrawal_service.withdraw_crypto()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["transaction_id"], "tx_456")

    @patch('app.services.transact.withdraw_crypto.withdraw_crypto.is_valid_address')
    @patch('app.services.transact.withdraw_crypto.withdraw_crypto.get_user_virtual_balance')
    def test_withdraw_crypto_invalid_address(self, mock_balance, mock_is_valid_address):
        mock_balance.return_value = Decimal("150.00")
        mock_is_valid_address.return_value = False

        result = self.withdrawal_service.withdraw_crypto()
        self.assertIn("error", result)
        self.assertEqual(result["error"], f"Invalid recipient address for user {self.user.id}: {self.recipient_address}")

if __name__ == "__main__":
    unittest.main()
