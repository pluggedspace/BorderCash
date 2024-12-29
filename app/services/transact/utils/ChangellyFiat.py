import base64
import json
import logging
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey
from typing import Any, Dict

from django.conf import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")


class ChangellyFiat:
    BASE_URL = "https://fiat-api.changelly.com/v1"

    def __init__(self, public_key: str, private_key: str) -> None:
        self.public_key = public_key
        self.private_key = self._load_private_key(private_key)

    @staticmethod
    def _load_private_key(self, private_key_base64: str) -> RSAPrivateKey:
        try:
            # Base64 decode the key
            private_key_bytes = base64.b64decode(private_key_base64)
            # Load the private key from the PEM bytes
            return serialization.load_pem_private_key(
                private_key_bytes,
                password=None,
            )
        except Exception as e:
            logging.error(f"Error loading private key: {e}")
            raise ValueError(
                "Could not deserialize key data. Ensure the private key is in correct PEM format and not encrypted.")

    def _get_signature(self, payload: str) -> str:
        """
        Create an RSA signature for the payload.
        """
        signature = self.private_key.sign(
            payload.encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode()

    def _get_headers(self, path: str, message: Dict[str, Any]) -> Dict[str, str]:
        """
        Prepare request headers including API key and signature.
        """
        payload = path + json.dumps(message, separators=(",", ":"))
        return {
            "Content-Type": "application/json",
            "X-Api-Key": self.public_key,
            "X-Api-Signature": self._get_signature(payload),
        }

    def _send_request(self, endpoint: str, method: str, message: Dict[str, Any]) -> Any:
        """
        Send a signed POST request to the Changelly Fiat API.
        """
        path = f"{self.BASE_URL}/{endpoint}"
        headers = self._get_headers(path, message)

        logging.info(f"Request to {endpoint}: {message}")
        response = requests.post(path, headers=headers, json=message)

        if response.ok:
            response_data = response.json()
            logging.info(f"Response from {endpoint}: {response_data}")
            return response_data

        raise Exception(
            f"Changelly API request error for {endpoint}: {response.status_code} {response.text}"
        )

    def get_available_countries(self) -> Any:
        """
        Fetch the list of available countries.
        """
        return self._send_request("available-countries", "POST", {})

    def get_supported_currencies(self) -> Any:
        """
        Fetch the list of supported currencies.
        """
        return self._send_request("currencies", "POST", {})

    def get_offers(self, pay_currency: str, receive_currency: str, amount: float) -> Any:
        """
        Fetch the best offers for a given currency pair and amount.
        """
        payload = {
            "payCurrency": pay_currency,
            "receiveCurrency": receive_currency,
            "amount": amount,
        }
        return self._send_request("offers", "POST", payload)

    def get_providers(self) -> Any:
        """
        Fetch the list of available providers.
        """
        return self._send_request("providers", "POST", {})

    def create_order(
        self, offer_id: str, wallet_address: str, kyc_accepted: bool, payment_method: str
    ) -> Any:
        """
        Create an order using the specified offer ID and return the redirect URL.
        """
        payload = {
            "offerId": offer_id,
            "address": wallet_address,
            "kycAccepted": kyc_accepted,
            "paymentMethod": payment_method,
        }
        return self._send_request("orders", "POST", payload)


"""changelly = ChangellyFiat(
        public_key=settings.CHANGELLY_FIAT_API_KEY,
        private_key=settings.CHANGELLY_FIAT_PRIVATE_KEY,
    )"""
