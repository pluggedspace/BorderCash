import logging
import threading
import time
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, Union, Any

import requests
from django.conf import settings
from django.db import transaction as db_transaction
from rest_framework.utils import timezone
from stellar_sdk import Server, Asset

from app.models import Transaction, USDAccount, PlatformAccount, User
from app.services.transact.utils.changelly_crypto import ChangellyClient
from app.services.transact.utils.fiat import ChangellyFiatApi
from app.services.transact.utils.utils import calculate_fee
from app.services.transact.utils.ChangellyFiat import ChangellyFiat

logger = logging.getLogger(__name__)


class TransakIntegrationError(Exception):
    """Custom exception for Transak integration errors"""
    pass


class ApiException(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class ValidationError(Exception):
    pass


class APIError(Exception):
    pass


class TransactionError(Exception):
    pass


changelly_client = ChangellyClient()


class DepositService:
    def __init__(self, user):
        self.user = user
        self.usd_account = USDAccount.objects.get(user=user)
        self.platform_account = PlatformAccount.objects.first()
        self.stellar_server = Server("https://horizon-testnet.stellar.org")
        self.custody_address = settings.PLATFORM_CUSTODY_STELLAR_ACCOUNT

        """self.api = ChangellyFiatApi(
                                    public_key=settings.CHANGELLY_FIAT_API_KEY,
                                    private_key=settings.CHANGELLY_FIAT_PRIVATE_KEY
                                )"""



    @staticmethod
    def is_valid_payment_method(payment_method):
        allowed_payment_methods = [
            "Faster Payment Bank Transfer", "Open Banking", "maya", "bpi",
            "grabpay", "shopeepay", "gcash", "pix", "astropay", "pse", "impa", "upi", "wire",

            "usdc", "credit_debit_card", "gbp_bank_transfer",
            "sepa_bank_transfer", "apple pay", "gpay", "transak"
        ]
        return payment_method in allowed_payment_methods

    @staticmethod
    def is_valid_gateway(gateway):
        gateways = [
            "usdc", "transak"
        ]
        return gateway in gateways

    # DIRECT STELLAR DEPOSIT
    def initiate_usdc_deposit(self, amount):
        try:
            # Convert amount to Decimal after ensuring it's a valid number
            amount = Decimal(amount) if isinstance(amount, (int, float, str)) else None
            if amount is None:
                raise ValueError("Invalid amount format")

            # Calculate fee
            total_amount, fee, net_amount = calculate_fee('deposit', amount)

            # Proceed with creating the transaction record and instructions
            memo = str(uuid.uuid4())[:12]

            pending_deposit = Transaction.objects.create(
                user=self.user,
                amount=amount,
                fee_amount=fee,
                memo=memo,
                transaction_type='deposit',
                status='pending',
                payment_method="stellar_usdc",
                gateway="usdc transfer",
                timestamp=timezone,
            )

            logger.info(f"Initiated USDC deposit: {pending_deposit.id}, Amount: {amount}, User: {self.user}")

        except (InvalidOperation, ValueError) as e:
            logger.error(f"Invalid amount: {amount} - Error: {e}")
            return None, None
        except Exception as e:
            logger.error(f"Unexpected error during deposit initiation: {e}")
            return None, None

        """ replace assets with this
        "asset": Asset("USDC", "GBBD47IFOR25FKLPAG42V6J33ZZW3DELPWZXX4SAEYZ35A6KTUV7USDC")
        """

        instructions = {
            "amount": amount,
            "asset": "USDC",
            "destination_address": settings.PLATFORM_CUSTODY_STELLAR_ACCOUNT,
            "memo": memo,
            "memo_type": "text"
        }

        threading.Thread(target=self.poll_for_deposit_confirmation, args=(pending_deposit.id,)).start()

        return instructions, pending_deposit.id

    def poll_for_deposit_confirmation(self, pending_deposit_id):
        while True:
            time.sleep(30)  # Polling interval

            result = self.confirm_usdc_deposit(pending_deposit_id)
            if result['status'] in ['success', 'error']:
                break  # Stop polling if confirmed or error occurs

    def confirm_usdc_deposit(self, pending_deposit_id):
        try:
            pending_deposit = Transaction.objects.get(id=pending_deposit_id)

            if pending_deposit.status != 'pending':
                logger.warning(f"Deposit {pending_deposit_id} is no longer pending.")
                return {"status": "error", "message": "This deposit is no longer pending."}

            payments = self.stellar_server.payments().for_account(
                settings.PLATFORM_CUSTODY_STELLAR_ACCOUNT).include_failed(
                False).limit(50).order(desc=True).call()

            usdc_asset = Asset("USDC", settings.USDC_ISSUER_PUBLIC_KEY)

            for payment in payments['_embedded']['records']:
                if (payment['type'] == 'payment' and
                        payment['to'] == settings.PLATFORM_CUSTODY_STELLAR_ACCOUNT and
                        payment['asset_type'] == 'credit_alphanum4' and
                        payment['asset_code'] == 'USDC' and
                        payment['asset_issuer'] == settings.USDC_ISSUER_PUBLIC_KEY and
                        float(payment['amount']) == float(pending_deposit.amount) and
                        payment.get('memo') == pending_deposit.memo):
                    usdc_amount = Decimal(payment['amount'])
                    self.usd_account.credit(usdc_amount)
                    self.platform_account.credit(usdc_amount)

                    pending_deposit.status = 'completed'
                    pending_deposit.stellar_transaction_id = payment['transaction_hash']
                    pending_deposit.save()

                    # Log the completed deposit
                    logger.info(
                        f"Deposit confirmed: {pending_deposit.id}, Amount: {usdc_amount}, Transaction ID: "
                        f"{payment['transaction_hash']}")

                    Transaction.objects.create(
                        user=self.user,
                        amount=usdc_amount,
                        transaction_type='USDC deposit',
                        status='completed',
                        stellar_transaction_id=payment['transaction_hash']
                    )

                    return {"status": "success", "message": "Deposit confirmed and processed."}

            logger.info(f"Deposit {pending_deposit_id} not yet detected.")
            return {"status": "pending", "message": "Deposit not yet detected. Please try confirming again later."}

        except Exception as e:
            logger.error(f"Error confirming deposit {pending_deposit_id}: {str(e)}")
            return {"status": "error", "message": "An error occurred while confirming the deposit."}

    def reconcile_memo_less_deposit(self, sender_address, amount):
        amount = Decimal(str(amount))

        matching_deposits = Transaction.objects.filter(
            user=self.user,
            amount=amount,
            status='pending'
        ).order_by('-created_at')

        if not matching_deposits.exists():
            logger.warning(f"No matching pending deposit found for amount: {amount}.")
            return {"status": "error", "message": "No matching pending deposit found."}

        payments = self.stellar_server.payments().for_account(settings.PLATFORM_CUSTODY_STELLAR_ACCOUNT).include_failed(
            False).limit(200).order(desc=True).call()

        for payment in payments['_embedded']['records']:
            if (payment['type'] == 'payment' and
                    payment['from'] == sender_address and
                    payment['to'] == settings.PLATFORM_CUSTODY_STELLAR_ACCOUNT and
                    payment['asset_type'] == 'credit_alphanum4' and
                    payment['asset_code'] == 'USDC' and
                    payment['asset_issuer'] == settings.USDC_ISSUER_PUBLIC_KEY and
                    Decimal(payment['amount']) == amount):
                usdc_amount = Decimal(payment['amount'])
                self.usd_account.credit(usdc_amount)
                self.platform_account.credit(usdc_amount)

                pending_deposit = matching_deposits.first()
                pending_deposit.status = 'completed'
                pending_deposit.stellar_transaction_id = payment['transaction_hash']
                pending_deposit.reconciled_at = timezone.now()
                pending_deposit.save()

                logger.info(
                    f"Reconciled deposit: {pending_deposit.id}, Amount: {usdc_amount}, Transaction ID: "
                    f"{payment['transaction_hash']}")

                Transaction.objects.create(
                    user=self.user,
                    amount=usdc_amount,
                    transaction_type='USDC deposit (reconciled)',
                    status='completed',
                    stellar_transaction_id=payment['transaction_hash']
                )

                return {"status": "success", "message": "Deposit reconciled and processed."}

        logger.warning(f"No matching transaction found on the Stellar network for amount: {amount}.")
        return {"status": "error", "message": "No matching transaction found on the Stellar network."}

    def list_unreconciled_deposits(self, days_back=30):
        end_time = timezone.now()
        start_time = end_time - timezone.timedelta(days=days_back)

        payments = self.stellar_server.payments().for_account(settings.PLATFORM_CUSTODY_STELLAR_ACCOUNT).include_failed(
            False).order(desc=True).call()

        unreconciled_deposits = []

        for payment in payments['_embedded']['records']:
            payment_time = timezone.datetime.strptime(payment['created_at'], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc)
            if payment_time < start_time:
                break

            if (payment['type'] == 'payment' and
                    payment['to'] == settings.PLATFORM_CUSTODY_STELLAR_ACCOUNT and
                    payment['asset_type'] == 'credit_alphanum4' and
                    payment['asset_code'] == 'USDC' and
                    payment['asset_issuer'] == settings.USDC_ISSUER_PUBLIC_KEY and
                    not payment.get('memo')):
                unreconciled_deposits.append({
                    'from': payment['from'],
                    'amount': payment['amount'],
                    'transaction_hash': payment['transaction_hash'],
                    'created_at': payment['created_at']
                })

        return unreconciled_deposits

    # CHANGELLY Crypto
    POLLING_INTERVAL = 30  # in seconds
    POLLING_TIMEOUT = 1800  # in seconds (30 minutes)

    @staticmethod
    def deposit_to_usdc(request, from_currency: str, amount: Union[Decimal, str, None]) -> Dict[str, Union[str, bool]]:
        """
        Deposit a specified currency and convert to USDC on Stellar (USDCXLM).
        """
        try:
            # Step 0: Extract and verify user
            user = request.user
            if not user or not isinstance(user, User):
                raise ValueError("Invalid or unauthenticated user")

            # Step 1: Validate input parameters (currency and amount)
            if not from_currency or not isinstance(from_currency, str):
                raise ValueError("Currency must be a non-empty string")

            if amount is None:
                raise ValueError("Amount cannot be None")

            # Convert amount to Decimal
            try:
                amount = Decimal(amount.strip()) if isinstance(amount, str) else Decimal(amount)
                if amount <= 0:
                    raise ValueError("Amount must be greater than 0")
            except (InvalidOperation, TypeError, ValueError) as e:
                raise ValueError(f"Invalid amount format: {str(e)}")

            # Step 2: Check if currency is supported
            supported_currencies = changelly_client.get_supported_currencies()
            if from_currency.upper() not in [c.upper() for c in supported_currencies]:
                raise ValueError(f"Currency {from_currency} is not supported by Changelly")

            # Step 3: Validate and get platform Stellar address
            stellar_address = settings.PLATFORM_CUSTODY_STELLAR_ACCOUNT
            if not stellar_address:
                raise ValueError("Invalid platform Stellar address configuration")

            # Step 4: Calculate exchange amount
            to_currency = "USDCXLM"
            estimated_amount_data = changelly_client.get_exchange_amount(
                from_currency=from_currency.lower(),
                to_currency=to_currency.lower(),
                amount=str(amount)
            )

            exchange_data = estimated_amount_data[0]
            estimated_amount = exchange_data.get('amountTo')
            network_fee = exchange_data.get('networkFee')
            rate = exchange_data.get('rate')
            transaction_fee = exchange_data.get('fee')

            if not estimated_amount or Decimal(estimated_amount) <= 0:
                raise ValueError("Invalid exchange rate received from Changelly")

            # Step 5: Create Changelly transaction
            with db_transaction.atomic():
                changelly_tx = changelly_client.create_transaction(
                    from_currency=from_currency.lower(),
                    to_currency=to_currency.lower(),
                    amount=str(amount),
                    address=stellar_address
                )

                # Ensure valid transaction response with transaction ID and deposit address
                transaction_id = changelly_tx.get("id")
                deposit_address = changelly_tx.get("payinAddress")
                if not transaction_id or not deposit_address:
                    raise ValueError("Failed to create Changelly transaction or retrieve deposit address")

                # Record transaction in the database
                db_transaction_record = Transaction.objects.create(
                    user=user,
                    gateway="Changelly",
                    transaction_id=transaction_id,
                    transaction_type='deposit',
                    currency_from=from_currency.upper(),
                    amount=Decimal(estimated_amount),
                    currency="USDC",
                    status="PENDING",
                    destination_account=stellar_address,
                    payment_method="crypto",
                )

                # Trigger polling in a separate thread
                threading.Thread(target=DepositService.poll, args=(transaction_id, db_transaction_record.id)).start()

                # Return detailed response
                return {
                    "success": True,
                    "message": "Deposit initiated successfully",
                    "transaction_id": transaction_id,
                    "deposit_details": {
                        "from_currency": from_currency,
                        "to_currency": to_currency,
                        "original_amount": str(amount),
                        "estimated_usdc": estimated_amount,
                        "network_fee": network_fee,
                        "rate": rate,
                        "transaction_fee": transaction_fee,
                        "deposit_address": deposit_address
                    }
                }

        except ValueError as ve:
            logging.error(f"Validation error: {ve}", exc_info=True)
            return {"success": False, "error": str(ve)}

        except Exception as e:
            logging.error(f"Unexpected error: {e}", exc_info=True)
            return {"success": False, "error": "An unexpected error occurred. Please try again later."}

    @staticmethod
    def poll(transaction_id: str, db_transaction_record_id: int):
        """
        Poll the status of a Changelly transaction until it is confirmed or fails.
        Updates USDAccount and PlatformAccount if the transaction is successful.
        """
        start_time = datetime.now()

        try:
            while True:
                # Check timeout
                elapsed_time = (datetime.now() - start_time).total_seconds()
                if elapsed_time > DepositService.POLLING_TIMEOUT:
                    logger.warning(f"Polling timeout for transaction {transaction_id}")
                    Transaction.objects.filter(id=db_transaction_record_id).update(
                        status="FAILED", updated_at=datetime.now()
                    )
                    break

                # Get transaction status
                result = changelly_client.get_transaction_status(transaction_id)
                logger.info(f"Transaction status response: {result}")

                # Handle list or dict response
                if isinstance(result, list) and len(result) > 0:
                    status = result[0].get("status")
                elif isinstance(result, dict):
                    status = result.get("status")
                else:
                    raise ValueError("Unexpected response format for transaction status")

                if status in ["success", "failed", "expired"]:
                    system_status = "SUCCESS" if status == "success" else "FAILED"
                    Transaction.objects.filter(id=db_transaction_record_id).update(
                        status=system_status, updated_at=datetime.now()
                    )

                    # Handle successful transaction
                    if status == "success":
                        DepositService.update_balances(db_transaction_record_id)

                    logger.info(f"Transaction {transaction_id} finalized with status: {status}")
                    break

                logger.info(f"Polling transaction {transaction_id}, status: {status}")
                time.sleep(DepositService.POLLING_INTERVAL)

        except Exception as e:
            logger.error(f"Error polling transaction {transaction_id}: {e}", exc_info=True)
            Transaction.objects.filter(id=db_transaction_record_id).update(
                status="ERROR", updated_at=datetime.now()
            )

    @staticmethod
    def update_balances(transaction_id: int):
        """
        Update the USDAccount and PlatformAccount balances after a successful deposit.
        """
        try:
            # Fetch the transaction record
            transaction = Transaction.objects.get(id=transaction_id)

            # Update the user's USDAccount balance
            user_account = USDAccount.objects.get(user=transaction.user)
            user_account.balance += transaction.amount
            user_account.save()

            # Update the platform's USD balance
            platform_account = PlatformAccount.objects.get(name="Pool", currency="USD")
            platform_account.balance += transaction.amount
            platform_account.save()

            logger.info(f"Balances updated successfully for transaction {transaction_id}: "
                        f"User Balance: {user_account.balance}, Platform Balance: {platform_account.balance}")
        except USDAccount.DoesNotExist:
            logger.error(f"USDAccount not found for user: {transaction.user}")
        except PlatformAccount.DoesNotExist:
            logger.error("PlatformAccount not found for USD")
        except Exception as e:
            logger.error(f"Error updating balances for transaction {transaction_id}: {e}", exc_info=True)

    # Linkio

    # Fetch vendors
    @staticmethod
    def fetch_vendors(currency):
        """
        Fetch the list of supported vendor bank account details.

        Args:
            currency (str): The currency for which vendors are fetched (default: NGN).

        Returns:
            list: A list of vendor details.
        """
        url = "https://api.linkio.world/transactions/v1/vendors"
        headers = {
            "accept": "application/json",
            "ngnc-sec-key": "ngnc_s_lk_d770850270259aa81a4ac216016f490f39515da7330b83dd380e3c17a1e348fa",
        }
        params = {"currency": currency}
        response = requests.get(url, headers=headers, params=params)

        # Check response status
        if response.status_code == 200:
            data = response.json()
            print("API Response:", data)  # Debugging log

            # Ensure "Vendors" key exists and contains data
            if "Vendors" in data and isinstance(data["Vendors"], list):
                return data["Vendors"]
            else:
                raise ValueError("No vendors found or unexpected response structure.")
        else:
            response.raise_for_status()

    @staticmethod
    def initiate_link_deposit(amount, currency, stables="usdc", network="Stellar", request=None):
        # Fetch the user from the request if provided
        user = request.user if request else None

        # Define the URL at the beginning of the method
        url = "https://api.linkio.world/transactions/v1/onramp"

        # Fetch vendor details
        vendors = DepositService.fetch_vendors(currency=currency)

        # Check if vendors are available
        if not vendors or len(vendors) == 0:
            raise ValueError("No vendors available for the selected currency.")

        # Auto-fill vendor details using the first available vendor
        vendor = vendors[0]
        vendor_name = vendor.get("venderName", "Unknown")
        vendor_number = vendor.get("vendorNumber", "Unknown")
        vendor_bank = vendor.get("vendorBank", "Unknown")

        
        # Prepare payload
        try:
            amount_decimal = Decimal(str(amount))
        except InvalidOperation:
            raise ValueError("Invalid amount format received from API.")

        # Prepare payload
        payload = {
            "business_id": "459990459",
            "type": "buy_ramp",
            "currency": currency,
            "amount": str(amount_decimal),
            "stables": stables,
            "vendor_bank": vendor_bank,
            "vendor_number": vendor_number,
            "vendor_name": vendor_name,
            "wallet_address": settings.PLATFORM_CUSTODY_STELLAR_ACCOUNT,
            "network": network,
        }
        headers = {
            "accept": "application/json",
            "ngnc-sec-key": "ngnc_s_lk_d770850270259aa81a4ac216016f490f39515da7330b83dd380e3c17a1e348fa",
            "content-type": "application/json",
        }

        # Send POST request
        try:
            response = requests.post(url, json=payload, headers=headers)

            # Log full response for debugging
            print(f"Full API Response Status Code: {response.status_code}")
            print(f"Full API Response Content: {response.text}")

            # Check response status
            if response.status_code not in [200, 201]:
                raise ValueError(f"API returned status code {response.status_code}")

            # Parse response
            transaction_data = response.json()

            # Extract reference from nested transaction key
            transaction_reference = transaction_data.get('transaction', {}).get('reference')

            if not transaction_reference:
                raise ValueError(f"No transaction reference found. Full response: {transaction_data}")

            print(f"Transaction Reference: {transaction_reference}")

            #fee = calculate_fee('deposit', amount)

            # Record the transaction if user is authenticated
            if user and user.is_authenticated:
                with db_transaction.atomic():
                    transaction = Transaction(
                        user=user,
                        amount=amount_decimal,
                        currency=currency,
                        transaction_id=transaction_reference,
                        status="Processing",
                        payment_method="Bank Transfer",
                        gateway="Link",
                        target_currency="USDC",
                        transaction_type="Deposit",
                        #fee_amount=fee,
                    )
                    transaction.save()

                    # Start polling only if user is authenticated
                    threading.Thread(target=DepositService.poll_transaction_status,
                                     args=(transaction_reference, user, transaction.id, amount)).start()

            return transaction_data

        except requests.RequestException as e:
            # Catch and log any request-related exceptions
            print(f"Request Error: {e}")
            raise ValueError(f"Failed to complete deposit request: {e}")
        except ValueError as e:
            # Re-raise value errors with context
            print(f"Deposit Initiation Error: {e}")
            raise

    @staticmethod
    def poll_transaction_status(transaction_reference, user, transaction_id, amount):
        """
        Polls the transaction status every 30 seconds until confirmed or timeout.

        Args:
            amount
            transaction_reference (str): The unique reference ID of the transaction.
            user (User): The user object associated with the transaction.
            transaction_id (int): The ID of the transaction to update.

        Returns:
            None
        """
        # Time interval for polling (in seconds)
        polling_interval = 60  # 1 minute
        timeout = 600  # 10 minutes timeout
        start_time = time.time()  # Record the start time

        # Log the start of polling
        print(f"Polling started for transaction {transaction_reference}.")

        # Keep polling until the transaction is successful or timeout is reached
        while True:
            # If timeout is reached, break out of the loop
            if time.time() - start_time > timeout:
                print(f"Polling timed out after {timeout} seconds.")
                break

            try:
                # Fetch the transaction status
                transaction_data = DepositService.fetch_transaction_status(transaction_reference)

                # Check if the transaction status is 'success'
                status = transaction_data.get("transaction_status")
                if status == "success":
                    print(f"Transaction {transaction_reference} confirmed successfully!")

                    # Update the transaction model with status 'success'
                    transaction = Transaction.objects.get(id=transaction_id)
                    transaction.status = "Success"
                    transaction.save()

                    # Now update the user's USDAccount balance
                    user_usd_account = USDAccount.objects.get(user=user)

                    # Subtract the calculated fee from the payout amount
                    fee_amount = calculate_fee('deposit', amount)  # Assuming 'amount' is the deposit amount
                    payout_amount = float(
                        transaction_data.get("payout_amount", 0))  # Get the payout amount (ensure it's a float)

                    # Deduct the fee from the payout amount before updating the balance
                    user_usd_account.balance += (payout_amount - fee_amount)

                    user_usd_account.save()

                    platform_account = PlatformAccount.objects.get(name="Fees")
                    platform_account.balance += fee_amount
                    platform_account.save()

                    try:
                        platform_account = PlatformAccount.objects.get(name="Pool")
                        platform_account.balance += transaction_data.get("payout_amount", 0)
                        platform_account.save()
                    except PlatformAccount.DoesNotExist:
                        print("Platform account with name 'pool' not found.")

                    break
                else:
                    print(f"Transaction is still {status}. Rechecking in {polling_interval} seconds...")

            except ValueError as e:
                print(f"Error fetching transaction status: {e}")
                break  # Stop polling if an error occurs

            # Wait for the next polling interval
            time.sleep(polling_interval)

    @staticmethod
    def fetch_transaction_status(transaction_reference):
        """
        Fetch the status of a transaction using its reference.

        Args:
            transaction_reference (str): The unique reference ID of the transaction.

        Returns:
            dict: The transaction details, including its status.

        Raises:
            ValueError: If the transaction is not found or an error occurs.
        """
        bus_id = "459990459"  # Replace with your business ID
        url = f"https://api.linkio.world/transactions/v1/fetch_transaction"
        params = {
            "business_id": bus_id,
            "transaction_reference": transaction_reference
        }
        headers = {
            "accept": "application/json",
            "ngnc-sec-key": "ngnc_s_lk_d770850270259aa81a4ac216016f490f39515da7330b83dd380e3c17a1e348fa",
            "content-type": "application/json",
        }

        # Send GET request to fetch transaction status
        response = requests.get(url, headers=headers, params=params)

        if response.status_code == 200:
            transaction_data = response.json()
            print("Transaction Data:", transaction_data)  # Debugging log

            # Ensure the response structure is as expected
            try:
                # Access the 'transaction_status' inside 'transactions' object
                transaction_status = transaction_data['transactions']['transaction_status']

                # If transaction is successful
                if transaction_status == "success":
                    return transaction_data
                else:
                    raise ValueError(f"Transaction is still {transaction_status}.")

            except KeyError as e:
                raise ValueError(f"Error in response structure: Missing expected key {e}")

        else:
            response.raise_for_status()

    