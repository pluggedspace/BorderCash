import logging
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Dict, Any, Union, Optional, Callable

import requests
from django.conf import settings
from django.db import transaction as txn
from stellar_sdk import Server, Asset, Keypair, TransactionBuilder, Network, Payment
from stellar_sdk.exceptions import BadRequestError, NotFoundError

from app.models import Transaction, USDAccount, PlatformAccount, User
from app.services.transact.utils.changelly_crypto import ApiService
from app.services.transact.utils.config_changelly import STELLAR_SERVER, STELLAR_SECRET_KEY
from app.services.transact.utils.utils import calculate_fee
from swif.settings import CHANGELLY_FIAT_URL

logger = logging.getLogger(__name__)


@dataclass
class TransactionResponse:
    status: str
    message: str
    error_code: Optional[str] = None
    transaction_hash: Optional[str] = None
    response: Optional[Dict] = None


class WithdrawalError(Exception):
    """Custom exception for withdrawal-related errors"""
    pass


class TransactionStatus(Enum):
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"


class WithdrawalService:
    def __init__(self, user):
        self.user = user
        self.usd_account = USDAccount.objects.get(user=user)
        self.platform_account = PlatformAccount.objects.first()
        self.stellar_server = Server("https://horizon-testnet.stellar.org")
        self.api_service = ApiService()
        self.swif_pool_account = settings.PLATFORM_CUSTODY_STELLAR_ACCOUNT
        self.swif_pool_keypair = Keypair.from_secret(settings.STELLAR_PLATFORM_SECRET)
        self.stellar_network = Network.TESTNET_NETWORK_PASSPHRASE

    # DIRECT STELLAR WITHDRAWAL
    def validate_stellar_address(self, address: str) -> bool:
        """Validate Stellar account address."""
        try:
            # Check if the account is valid by attempting to load it
            self.stellar_server.load_account(address)
            return True
        except Exception as e:
            logger.error(f"Error validating Stellar address '{address}': {str(e)}")
            return False

    def withdraw_stellar(self, amount: Decimal, destination_account: str, transaction_id: str) -> Dict[str, Any]:
        """
        Withdraw the specified amount of USDC from the pooled Stellar account to the given destination account.

        :param amount: The amount of USDC to withdraw.
        :param destination_account: The Stellar account to which the USDC will be sent.
        :param transaction_id: A unique ID for the transaction.
        :return: A dictionary containing transaction details or an error message.
        """

        try:
            amount = Decimal(str(amount))
        except (TypeError, InvalidOperation):
            return {"error": "Invalid amount format."}

        # Validate amount
        if amount <= 0:
            return {"error": "Amount must be greater than zero."}

        """# Check user's USD account balance
        if self.usd_account.balance < amount:
            return {"error": "Insufficient balance."}"""

        # Use a database transaction to ensure atomicity
        with txn.atomic():
            # Check if the transaction already exists
            if Transaction.objects.filter(user=self.user, transaction_id=transaction_id).exists():
                return {"error": "Duplicate transaction detected."}

            # Calculate fees
            try:
                total_amount, fee_amount, net_amount = calculate_fee('withdrawal', amount)

                # Check if user has enough balance for the withdrawal + fee
                if self.usd_account.balance < (amount + fee_amount):
                    return {"error": "Insufficient balance after fees."}

                # Deduct the amount + fee
                self.usd_account.balance -= (amount + fee_amount)
                self.usd_account.save()

            except ValueError as e:
                logger.error(f"Fee calculation error: {str(e)}")
                return {"error": "Error calculating fees."}

            # Update platform fees account
            platform_fee_account = PlatformAccount.objects.filter(name="Fees").first()
            if platform_fee_account:
                platform_fee_account.balance += fee_amount
                platform_fee_account.save()
            else:
                logger.error("No fee account found in PlatformAccount.")

            # Load the user's Stellar keypair
            user_keypair = Keypair.from_secret(settings.STELLAR_PLATFORM_SECRET)

            # Validate the destination account
            if not self.validate_stellar_address(destination_account):
                return {"error": "Invalid destination Stellar account."}

            # Create the transaction
            try:
                pooled_account = self.stellar_server.load_account(settings.PLATFORM_CUSTODY_STELLAR_ACCOUNT)

                # Create the Payment operation for the net amount
                payment_operation = Payment(
                    destination=destination_account,
                    asset=Asset("USDC", settings.USDC_ISSUER_PUBLIC_KEY),
                    amount=str(net_amount)
                )

                # Build the transaction
                transaction = (
                    TransactionBuilder(
                        source_account=pooled_account,
                        network_passphrase=Network.TESTNET_NETWORK_PASSPHRASE,
                        base_fee=100
                    )
                    .append_operation(payment_operation)
                    .set_timeout(30)
                    .build()
                )

                # Sign the transaction
                transaction.sign(user_keypair)

                # Submit the transaction
                response = self.stellar_server.submit_transaction(transaction)

                # Log transaction details
                logger.info(f"Stellar transaction successful: {response['hash']}")

                # Save the transaction in your database
                Transaction.objects.create(
                    user=self.user,
                    amount=net_amount,
                    transaction_type='withdraw',
                    target_currency='USDC',
                    transaction_id=transaction_id  # Store the unique transaction ID

                )

                return {"success": True, "transaction_hash": response['hash']}

            except Exception as e:
                logger.error(f"Error during Stellar withdrawal: {str(e)}")
                return {"error": "Transaction failed.", "details": str(e)}

    # CHANGELLY_CRYPTO WITHDRAWAL

    # Maximum timeout for transaction in seconds
    TRANSACTION_TIMEOUT = 60
    # Maximum retries for API calls
    MAX_RETRIES = 3
    # Delay between retries in seconds
    RETRY_DELAY = 2

    # Main Changelly Crypto Withdrawal Method
    def process_crypto(self, amount: str, from_currency: str, target_currency: str, destination_account: str,
                       ) -> Dict:
        """
        Process a cryptocurrency withdrawal via Changelly with enhanced security and validation.
        Also records the transaction, deducts the user's balance, and updates the platform fee account.
        """
        try:
            logging.debug(f"Starting process_crypto with amount={amount}, from_currency={from_currency}, "
                          f"target_currency={target_currency}, destination_account={destination_account}")

            validated_amount = self._validate_amount(amount)
            self._validate_currencies(from_currency, target_currency)
            self._validate_destination(destination_account)

            self._check_user_balance(validated_amount)

            exchange_estimate = self._retry_operation(
                lambda: self.api_service.get_exchange_amount(
                    from_currency, target_currency, str(validated_amount)
                )
            )
            logging.debug(f"Exchange estimate: {exchange_estimate}")

            self._retry_operation(
                lambda: self._validate_destination_address(
                    target_currency, destination_account
                )
            )

            transaction_details = self._retry_operation(
                lambda: self._create_changelly_transaction(
                    validated_amount, from_currency, target_currency, destination_account
                )
            )
            logging.debug(f"Transaction details: {transaction_details}")

            # Now that the trustline is ensured, process the USDC transfer
            transfer_result = self._process_usdc_transfer(
                validated_amount,
                transaction_details['payinAddress'],
                transaction_details.get('payinExtraId')
            )

            logging.debug(f"Transfer result: {transfer_result}")

            # Poll the transaction status after initiating the transfer
            transaction_id = transfer_result.transaction_hash  # Assuming this is the ID to track
            status = self.poll_transaction_status(transaction_id)  # Call the polling method

            logging.debug(f"Transaction {transaction_id} status after polling: {status}")

            # If transaction is successful, record it and deduct the user's balance
            if status == "completed":  # You may need to map this to actual status codes.
                # Record the transaction in the Transaction model
                transaction = Transaction.objects.create(
                    user=User,  # Assuming the user is identified by `user_id`
                    amount=validated_amount,
                    from_currency=from_currency,
                    transaction_type='withdraw',
                    target_currency=target_currency,
                    status=TransactionStatus.SUCCESS.value,
                    transaction_hash=transaction_id,
                    destination_account=destination_account
                )

                # Deduct the amount from the user's balance
                user = User.objects.get()  # Retrieve the user object
                user_balance = user.usd_account.balance  # Assuming balance is in USDAccount model
                user_balance -= validated_amount  # Deduct the amount
                user.usd_account.save()  # Save the updated balance

                # Calculate and deduct the platform fee
                platform_fee_percentage = 0.02  # Example: 2% fee, modify as per your fee structure
                fee_amount = validated_amount * platform_fee_percentage

                # Update the platform fees account
                platform_fee_account = PlatformAccount.objects.filter(name="Fees").first()
                if platform_fee_account:
                    platform_fee_account.balance += fee_amount
                    platform_fee_account.save()
                    logging.debug(f"Platform fee of {fee_amount} added to the platform fee account.")
                else:
                    logging.error("No fee account found in PlatformAccount.")

                logging.debug(f"Transaction recorded, user balance updated, and platform fee deducted.")

                return {
                    "status": TransactionStatus.SUCCESS.value,
                    "message": "Transaction processed successfully",
                    "exchange_estimate": exchange_estimate,
                    "target_currency": target_currency,
                    "target_address": destination_account,
                    "transaction_hash": transfer_result.transaction_hash,
                    "transaction_status": status
                }

            else:
                logging.error(f"Transaction failed with status: {status}")
                return {
                    "status": TransactionStatus.ERROR.value,
                    "message": "Transaction failed"
                }

        except WithdrawalError as e:
            logging.error(f"Withdrawal error: {str(e)}")
            return {"status": TransactionStatus.ERROR.value, "message": str(e)}
        except Exception as e:
            logging.error(f"Unexpected error in withdrawal: {str(e)}", exc_info=True)
            return {
                "status": TransactionStatus.ERROR.value,
                "message": "An unexpected error occurred"
            }

    @staticmethod
    def _validate_amount(amount: str) -> Decimal:
        """Validate and convert amount with strict checking"""
        logging.debug(f"Validating amount: {amount}")
        if not amount:
            raise WithdrawalError("Amount is required")
        try:
            validated_amount = Decimal(amount)
            if validated_amount <= 0:
                raise WithdrawalError("Amount must be greater than zero")
            return validated_amount
        except (ValueError, InvalidOperation):
            logging.error(f"Invalid amount format: {amount}")
            raise WithdrawalError("Invalid amount format")

    @staticmethod
    def _validate_currencies(from_currency: str, target_currency: str) -> None:
        """Validate currency codes"""
        logging.debug(f"Validating currencies: from_currency={from_currency}, target_currency={target_currency}")
        if not all([from_currency, target_currency]):
            raise WithdrawalError("Currency codes are required")
        if from_currency.lower() != 'usdcxlm':
            raise WithdrawalError("Source currency must be USDC on Stellar")

    @staticmethod
    def _validate_destination(destination: str) -> None:
        """Validate destination address format"""
        logging.debug(f"Validating destination address: {destination}")
        if not destination or len(destination) < 32:
            raise WithdrawalError("Invalid destination address format")

    def _check_user_balance(self, amount: Decimal) -> None:
        """Check user balance with atomic operation"""
        logging.debug(f"Checking user balance for amount: {amount}")
        from django.db import transaction
        with transaction.atomic():
            user_account = USDAccount.objects.select_for_update().get(user=self.user)
            if user_account.balance < amount:
                logging.error(f"Insufficient balance: {user_account.balance} < {amount}")
                raise WithdrawalError("Insufficient balance")

    def _retry_operation(self, operation: Callable, max_retries: Optional[int] = None,
                         retry_strategy: Optional[Callable] = None):
        """Retry mechanism for API operations with customizable strategies."""
        max_retries = max_retries or self.MAX_RETRIES
        retry_strategy = retry_strategy or (lambda attempt: time.sleep(self.RETRY_DELAY))

        logging.debug(f"Starting retry operation with max_retries={max_retries}")
        last_error = None

        for attempt in range(max_retries):
            try:
                return operation()
            except Exception as e:
                last_error = e
                logging.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    retry_strategy(attempt)

        logging.error(f"Operation failed after {max_retries} attempts: {str(last_error)}")
        raise WithdrawalError(f"Operation failed after {max_retries} attempts: {str(last_error)}")

    def _validate_destination_address(self, currency: str, address: str) -> None:
        """Validate destination address with Changelly API"""
        logging.debug(f"Validating destination address with Changelly API: currency={currency}, address={address}")
        is_valid = self.api_service.validate_address(currency, address)
        if not is_valid:
            logging.error(f"Invalid destination address: {address}")
            raise WithdrawalError("Invalid destination address")

    def _create_changelly_transaction(self, amount: Decimal, from_currency: str,
                                      to_currency: str, address: str) -> Dict:
        """Create transaction on Changelly"""
        logging.debug(f"Creating Changelly transaction: amount={amount}, from_currency={from_currency}, "
                      f"to_currency={to_currency}, address={address}")
        return self.api_service.create_transaction(
            from_currency=from_currency,
            to_currency=to_currency,
            amount=str(amount),
            address=address
        )

    @staticmethod
    def _build_transaction(amount: Decimal, changelly_address: str, memo: Optional[str] = None):
        """Build a Stellar transaction for sending USDC to Changelly."""
        if memo and len(memo) > 28:
            raise WithdrawalError("Memo exceeds the maximum length of 28 characters")

        try:
            # Set up Stellar server and keys
            platform_keypair = Keypair.from_secret(STELLAR_SECRET_KEY)
            platform_public_key = platform_keypair.public_key

            # Load platform account
            platform_account = STELLAR_SERVER.load_account(account_id=platform_public_key)
            base_fee = STELLAR_SERVER.fetch_base_fee()

            # Define the USDC asset
            usdc_asset = Asset("USDC", "GA5ZSEJYB37JRC5AVCIA5MOP4RHTM335X2KGX3IHOJAPP5RE34K4KZVN")

            # Verify the Changelly address exists
            try:
                STELLAR_SERVER.accounts().account_id(changelly_address).call()
            except NotFoundError:
                raise WithdrawalError(f"Changelly destination account {changelly_address} not found on Stellar network")
            except Exception as e:
                logging.error(f"Error verifying Changelly account: {str(e)}")
                raise WithdrawalError("Unable to verify Changelly account")

            # Build the transaction
            transaction = TransactionBuilder(
                source_account=platform_account,
                network_passphrase=Network.PUBLIC_NETWORK_PASSPHRASE,
                base_fee=base_fee
            )

            # Add the payment operation
            transaction.append_payment_op(
                destination=changelly_address,
                asset=usdc_asset,
                amount=str(amount)
            )

            # Add memo (required for Changelly routing)
            if memo:
                transaction.add_text_memo(memo)
            else:
                raise WithdrawalError("Memo is required for Changelly transactions")

            return transaction

        except Exception as e:
            logging.error(f"Error building Stellar transaction: {str(e)}")
            raise WithdrawalError(f"Failed to build transaction: {str(e)}")

    def _process_usdc_transfer(self, amount: Decimal, changelly_address: str,
                               payinExtraId: Optional[str]) -> TransactionResponse:
        """Process USDC transfer to Changelly with enhanced security"""
        try:
            transaction = self._build_transaction(amount, changelly_address, payinExtraId)
            signed_transaction = transaction.build()
            signed_transaction.sign(self.swif_pool_keypair)

            try:
                response = self.stellar_server.submit_transaction(signed_transaction)
            except BadRequestError as e:
                if "op_no_trust" in str(e):
                    logging.error(f"Trustline issue with Changelly address: {str(e)}")
                    raise WithdrawalError("Unable to process transaction. Please contact support.")
                raise

            if not response or 'hash' not in response:
                raise WithdrawalError("Failed to get transaction hash from Stellar response")

            return TransactionResponse(
                status=TransactionStatus.SUCCESS.value,
                message="Transaction submitted successfully",
                transaction_hash=response['hash'],
                response=response
            )

        except BadRequestError as e:
            error_msg = f"Stellar transaction failed: {str(e)}"
            logging.error(error_msg)
            raise WithdrawalError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error during transaction: {str(e)}"
            logging.error(error_msg)
            raise WithdrawalError(error_msg)

    # Method to poll transaction status from API
    def poll_transaction_status(self, transaction_id: str) -> Union[str, None]:
        url = f"{self.url}/v1/transaction/{transaction_id}/status"
        headers = {
            "Authorization": f"Bearer {self.x_api_key}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                status = response.json().get('status')
                logging.info(f"Transaction {transaction_id} status: {status}")
                return status
            logging.error(f"Error polling transaction {transaction_id}: {response.json().get('message')}")
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"Network error while polling transaction status: {str(e)}")
            return None

    # Link
    BASE_URL = "https://api.linkio.world/transactions/v1"

    # Step 1: Fetch Supported Banks
    @staticmethod
    def fetch_payment_banks(currency="NGN"):
        url = f"{WithdrawalService.BASE_URL}/live/list_payment_banks"
        response = requests.get(url, params={"currency": currency})
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to fetch banks: {response.text}")

    # Step 2: Initiate Off-Ramp Transaction
    @staticmethod
    def initiate_offramp_transaction(amount, currency, account_name, account_number, bank_name,
                                     network: str = "stellar",
                                     request_user=None) -> dict:
        # Ensure request_user is the authenticated User object
        if not request_user:
            raise ValueError("User is not authenticated or not provided.")
        """
        Initiates an offramp transaction through the Link API.
        """
        # Fetch the destination wallet address from the Link API
        wallet_response = WithdrawalService.fetch_payment_wallets()
        destination_wallet_address = wallet_response.get("wallet_address")
        if not destination_wallet_address:
            raise Exception("Failed to fetch destination wallet address.")

        # Prepare the payload for the Link API request
        payload = {
            "business_id": "459990459",
            "link_tag": "pluggedspace",
            "type": "sell_ramp",
            "stables": "USDC",
            "amount": amount,
            "currency": currency,
            "account_name": account_name,
            "account_number": account_number,
            "bank_name": bank_name,
            "network": network,
            "wallet_address": settings.PLATFORM_CUSTODY_STELLAR_ACCOUNT,
        }

        headers = {
            "accept": "application/json",
            "ngnc-sec-key": settings.LINK_API_KEY,
            "content-type": "application/json",
        }

        # Make the API request
        response = requests.post(f"{WithdrawalService.BASE_URL}/offramp", json=payload, headers=headers)

        if response.status_code in [200, 201]:
            response_data = response.json()
            if response_data.get("status") == "success" and response_data.get("code") == "TXN_SUCCESSFUL":

                # Parse response
                transaction_data = response.json()

                # Extract reference from nested transaction key
                transaction_reference = transaction_data.get('transaction', {}).get('reference')
                transaction_id = transaction_data.get('transaction', {}).get('transaction_id')

                # Record the transaction
                transaction = WithdrawalService.record_transaction(amount, "withdraw", "success", currency,
                                                                   transaction_reference, transaction_id, request_user)

                # Send from custody to destination wallet
                send_result = WithdrawalService.send_from_custody_to_destination(amount, destination_wallet_address)

                # Update balances
                WithdrawalService.update_user_balance(amount, request_user)
                WithdrawalService.update_pool_balance(amount)

                return send_result
            else:
                raise Exception(f"Transaction Failed: {response_data.get('message', 'Unknown error')}")
        else:
            raise Exception(f"Transaction Failed: {response.status_code} - {response.text}")

    @staticmethod
    def fetch_payment_wallets(currency: str = "USDC", network="Stellar"):
        url = "https://api.linkio.world/transactions/v1/live/list_payment_wallets"
        headers = {
            "accept": "application/json",
            "ngnc-sec-key": settings.LINK_API_KEY,
            "content-type": "application/json",
        }
        params = {"currency": currency, "network": network}
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                wallet_data = response.json()
                for wallet in wallet_data.get("Wallets", []):
                    if wallet["network"].lower() == network.lower():
                        return {"wallet_address": wallet["address"]}
                raise Exception(f"No wallet found for network: {network}")
            else:
                raise Exception(f"Failed to fetch payment wallets: {response.status_code} - {response.text}")
        except Exception as e:
            logging.error(f"Error fetching payment wallets: {str(e)}")
            raise

    @staticmethod
    def record_transaction(amount: float, transaction_type: str, status: str, currency: dict, transaction_reference,
                           transaction_id, user) -> Transaction:
        """
        Records the transaction in the database.
        """
        transaction = Transaction.objects.create(
            user_id=user.id,
            amount=amount,
            transaction_type=transaction_type,
            status=status,
            payment_method="Bank Transfer",
            gateway="Link",
            target_currency=currency,
            currency_from="USDC",
            external_reference=transaction_reference,
            transaction_id=transaction_id
        )
        return transaction

    @staticmethod
    def update_user_balance(amount: float, user) -> None:
        """
        Update the user's balance in the USDAccount model.
        """
        user_account = USDAccount.objects.get(user=user)
        user_account.balance -= amount
        user_account.save()

    @staticmethod
    def update_pool_balance(amount: float):
        """
        Update the PlatformAccount (Pool) balance.
        """
        pool_account = PlatformAccount.objects.get(account_name="Pool")
        pool_account.balance -= amount
        pool_account.save()

    @staticmethod
    def send_from_custody_to_destination(amount: float, destination_wallet_address: str) -> dict:
        """
        Sends the specified amount from the custody account to the destination wallet address.
        """
        try:
            # Fetch the destination wallet address
            server = Server(horizon_url="https://horizon.stellar.org")
            network = Network.PUBLIC_NETWORK_PASSPHRASE  # Use Network.TESTNET for testing

            # Define the custody account details
            custody_wallet_address = settings.PLATFORM_CUSTODY_STELLAR_ACCOUNT
            custody_secret_key = settings.STELLAR_PLATFORM_SECRET

            # Initialize the Keypair for the custody account
            custody_keypair = Keypair.from_secret(custody_secret_key)
            source_account = server.load_account(custody_wallet_address)

            # Create the USDC asset
            usdc_asset = Asset("USDC", "GCO6ZGZBGXJMQ3C43OS5YDRCZ7H3QJFNXYQ4ZMEF3PE7O5A4NZ5P")

            # Build the payment operation
            payment_op = source_account.payment(destination_wallet_address, amount=amount, asset=usdc_asset)

            # Create the transaction
            transaction = TransactionBuilder(source_account, network_passphrase=network) \
                .add_operation(payment_op) \
                .set_timeout(30) \
                .build()

            # Sign the transaction
            transaction.sign(custody_keypair)

            # Submit the transaction
            response = server.submit_transaction(transaction)

            # Return success response with the transaction result
            return {
                "status": "success",
                "transaction_hash": response["hash"],
                "destination_wallet_address": destination_wallet_address,
                "amount_sent": amount
            }

        except Exception as e:
            logging.error(f"Error: {str(e)}")
            raise Exception(f"Failed to send USDC from custody to destination: {str(e)}")

   