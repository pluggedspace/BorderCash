import base64
import binascii
import json
import logging
from decimal import Decimal
from typing import List, Dict, Union, Optional

from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from django.conf import settings
from requests import post, Response

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


# Custom exception class for handling API errors
class ApiException(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# Changelly's crypto deposit services
class ChangellyClient:
    def __init__(self):
        self.url = settings.CHANGELLY_API_URL
        self.private_key = settings.CHANGELLY_API_PRIVATE_KEY
        self.x_api_key = settings.CHANGELLY_API_KEY

    def _sign_request(self, body: dict) -> str:
        """Sign the request body using the private key."""
        try:
            decoded_private_key = binascii.unhexlify(self.private_key)
            private_key = RSA.import_key(decoded_private_key)
            message = json.dumps(body).encode('utf-8')
            h = SHA256.new(message)
            signature = pkcs1_15.new(private_key).sign(h)
            return base64.b64encode(signature).decode('utf-8')
        except (ValueError, binascii.Error, Exception) as e:
            logging.error("Failed to sign request: %s", e)
            raise ApiException(500, "Signing error")

    def _get_headers(self, body: dict) -> dict:
        """Generate headers for the API request."""
        signature = self._sign_request(body)
        return {
            'content-type': 'application/json',
            'X-Api-Key': self.x_api_key,
            'X-Api-Signature': signature,
        }

    def _request(self, method: str, params: dict or list = None):
        """Send a JSON-RPC request to the Changelly API."""
        params = params if params else {}
        message = {
            'jsonrpc': '2.0',
            'id': 'test',
            'method': method,
            'params': params
        }
        try:
            response = post(self.url, headers=self._get_headers(body=message), json=message)
            response.raise_for_status()
            response_body = response.json()
            if 'error' in response_body:
                error = response_body['error']
                raise ApiException(error['code'], error['message'])
            return response_body.get('result')
        except ApiException as e:
            logging.error("Changelly API error (method %s): %s", method, e.message)
            raise
        except Exception as e:
            logging.error("Request error (method %s): %s", method, e)
            raise ApiException(500, f"Request to Changelly failed: {str(e)}")

    def get_supported_currencies(self):
        """Fetch the list of supported currencies."""
        return self._request('getCurrencies')

    def get_exchange_amount(self, from_currency: str, to_currency: str, amount: str):
        """Get estimated amount after fees for a currency exchange."""
        from_currency = from_currency.lower()
        to_currency = to_currency.lower()
        params = [{
            "from": from_currency,
            "to": to_currency,
            "amountFrom": amount.strip()
        }]

        response = self._request("getExchangeAmount", params=params)

        # Debugging the response
        print(response)
        return response

    def create_transaction(self, from_currency: str, to_currency: str, amount: str, address: str,
                           extra_id: Optional[str] = None):
        """Create a new exchange transaction."""
        logger.debug(f"Creating Changelly transaction with params: {from_currency}, {to_currency}, {amount}, {address}")

        # Validate currencies and amount
        supported_currencies = self.get_supported_currencies()
        if from_currency.lower() not in supported_currencies:
            raise ValueError(f"Currency {from_currency} is not supported for exchange.")
        if to_currency.lower() not in supported_currencies:
            raise ValueError(f"Currency {to_currency} is not supported for exchange.")

        # Ensure amount is valid
        try:
            amount_float = float(amount)
            if amount_float <= 0:
                raise ValueError(f"Invalid amount: {amount}. It must be a positive number.")
        except ValueError:
            raise ValueError(f"Invalid amount: {amount}. It must be a valid number.")

        # Build the params dictionary, including optional extra_id if provided
        params = {
            "from": from_currency.lower(),
            "to": to_currency.lower(),
            "amountFrom": str(amount),  # Ensure this is a string
            "address": address,
        }
        if extra_id:
            params["extraId"] = extra_id

        # Log params for debugging
        logger.debug(f"Parameters for Changelly createTransaction: {params}")

        # Send request to Changelly API
        try:
            changelly_response = self._request("createTransaction", params=params)
            logger.debug(f"Changelly transaction created successfully: {changelly_response}")
            return changelly_response
        except ApiException as e:
            logger.error(f"Changelly API error (createTransaction): {e.message}")
            raise ValueError(f"Changelly API error: {e.message}")
        except Exception as e:
            logger.error(f"Unexpected error creating Changelly transaction: {e}")
            raise ValueError("Failed to create transaction with Changelly")

    def get_transaction_status(self, transaction_id: str):
        """Check the status of a specific transaction."""
        params = {"id": transaction_id}
        return self._request("getTransactions", params=params)


class ApiService:
    def __init__(self):
        self.url = settings.CHANGELLY_API_URL
        self.private_key = settings.CHANGELLY_API_PRIVATE_KEY
        self.x_api_key = settings.CHANGELLY_API_KEY

        # Ensure all required attributes are set
        if not self.url or not self.private_key or not self.x_api_key:
            raise ValueError("API URL, private key, and API key must all be provided.")

    def _request(self, method: str, params: Union[Dict, List] = None) -> Union[Response, List[Dict]]:
        params = params if params else {}
        message = {
            'jsonrpc': '2.0',
            'id': 'test',
            'method': method,
            'params': params
        }
        response = post(self.url, headers=self._get_headers(body=message), json=message)
        if response.ok:
            response_body = response.json()
            logging.info(f'{method} response: {response_body} (request: {params})')
            if response_body.get('error'):
                error = response_body['error']
                raise ApiException(error['code'], error['message'])
            return response_body['result']
        raise ApiException(response.status_code, response.text)

    def _sign_request(self, body: dict) -> str:
        try:
            # Convert Decimals to strings in the body
            def decimal_to_str(o):
                return str(o) if isinstance(o, Decimal) else o

            # Use a custom encoder function that converts Decimal values
            message = json.dumps(body, default=decimal_to_str).encode('utf-8')

            decoded_private_key = binascii.unhexlify(self.private_key)
            private_key = RSA.import_key(decoded_private_key)
            h = SHA256.new(message)
            signature = pkcs1_15.new(private_key).sign(h)
            return base64.b64encode(signature).decode('utf-8')
        except (ValueError, TypeError) as e:
            logging.error(f"Failed to sign request: {e}")
            raise ApiException(500, "Internal error while signing request")

    def _get_headers(self, body: dict) -> dict:
        signature = self._sign_request(body)
        return {
            'content-type': 'application/json',
            'X-Api-Key': self.x_api_key,
            'X-Api-Signature': signature,
        }

    def get_supported_currencies(self):
        """Fetch the list of supported currencies."""
        return self._request('getCurrencies')

    # Method to get exchange amount estimate
    def get_exchange_amount(self, from_currency: "USDCXLM", target_currency: str, amount: str):
        """Get estimated amount after fees for a currency exchange."""
        if amount is None:
            raise ValueError("Amount must not be None")

        params = [{
            "from": from_currency,
            "to": target_currency,
            "amountFrom": amount
        }]

        response = self._request("getExchangeAmount", params=params)
        print(response)  # Debugging the response
        return response

    # Method to validate the destination wallet address for a given currency
    def validate_address(self, currency: str, address: str):
        return self._request('validateAddress', params={
            'currency': currency,
            'address': address
        })

    # Method to create a transaction for currency conversion
    def create_transaction(self, from_currency: str, to_currency: str, amount: str, address: str,
                           extra_id: Optional[str] = None):
        """Create a new exchange transaction."""
        logger.debug(f"Creating Changelly transaction with params: {from_currency}, {to_currency}, {amount}, {address}")

        # Validate currencies and amount
        supported_currencies = self.get_supported_currencies()
        if from_currency.lower() not in supported_currencies:
            raise ValueError(f"Currency {from_currency} is not supported for exchange.")
        if to_currency.lower() not in supported_currencies:
            raise ValueError(f"Currency {to_currency} is not supported for exchange.")

        # Ensure amount is valid
        try:
            amount_float = float(amount)
            if amount_float <= 0:
                raise ValueError(f"Invalid amount: {amount}. It must be a positive number.")
        except ValueError:
            raise ValueError(f"Invalid amount: {amount}. It must be a valid number.")

        # Build the params dictionary, including optional extra_id if provided
        params = {
            "from": from_currency.lower(),
            "to": to_currency.lower(),
            "amountFrom": str(amount),  # Ensure this is a string
            "address": address,
        }
        if extra_id:
            params["extraId"] = extra_id

        # Log params for debugging
        logger.debug(f"Parameters for Changelly createTransaction: {params}")

        # Send request to Changelly API
        try:
            changelly_response = self._request("createTransaction", params=params)
            logger.debug(f"Changelly transaction created successfully: {changelly_response}")
            return changelly_response
        except ApiException as e:
            logger.error(f"Changelly API error (createTransaction): {e.message}")
            raise ValueError(f"Changelly API error: {e.message}")
        except Exception as e:
            logger.error(f"Unexpected error creating Changelly transaction: {e}")
            raise ValueError("Failed to create transaction with Changelly")

    # Method to fetch parameters for a specific currency pair
    def get_pairs_params(self, currency_from: str, currency_to: str):
        return self._request('getPairsParams', params=[{'from': currency_from, 'to': currency_to}])

    # Method to fetch transaction details or transaction history
    def get_transactions(self):
        return self._request('getTransactions', params={})
