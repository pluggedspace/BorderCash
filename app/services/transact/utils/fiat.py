import base64
import json
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from django.conf import settings

import logging

logger = logging.getLogger(__name__)


class ChangellyFiatApi:
    BASE_URL = "https://fiat-api.changelly.com/v1"

    def __init__(self):
        self.public_key = settings.CHANGELLY_FIAT_API_KEY
        self.private_key = serialization.load_pem_private_key(
            base64.b64decode(settings.CHANGELLY_FIAT_PRIVATE_KEY),
            password=None,
        )

    def create_signature(self, path: str, message: dict) -> str:
        payload = path + json.dumps(message, separators=(',', ':'))
        signature = self.private_key.sign(
            payload.encode(),
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode()

    def send_request(self, method: str, endpoint: str, body: dict = None):
        """
        Send an HTTP request to the API with proper authentication and error handling.

        Args:
            method (str): HTTP method ('get', 'post', 'put', 'delete')
            endpoint (str): API endpoint to call
            body (dict, optional): Request payload. Defaults to None.

        Returns:
            dict: Parsed JSON response from the API

        Raises:
            ValueError: For invalid HTTP methods
            requests.RequestException: For network or request-related errors
            APIError: For API-specific errors
        """
        # Normalize method to lowercase
        method = method.lower()

        # Validate HTTP method
        valid_methods = {'get', 'post', 'put', 'patch', 'delete'}
        if method not in valid_methods:
            raise ValueError(f"Invalid HTTP method. Must be one of {valid_methods}")

        # Ensure body is a dictionary
        body = body or {}

        # Construct full URL
        path = f"{self.BASE_URL}/{endpoint}"

        # Prepare headers
        signature = self.create_signature(path, body)
        headers = {
            "Content-Type": "application/json",
            "X-Api-Key": self.public_key,
            "X-Api-Signature": signature,
        }

        try:
            # Select and execute the appropriate request method
            request_method = getattr(requests, method)

            # Different handling for methods with/without body
            if method in {'get', 'delete'}:
                response = request_method(path, headers=headers)
            else:
                response = request_method(path, headers=headers, json=body)

            # Log the request details for debugging
            logger.debug(f"API Request: {method.upper()} {path}")
            logger.debug(f"Request Headers: {headers}")
            logger.debug(f"Request Body: {body}")

            # Check response
            if response.ok:
                # Log successful response
                logger.debug(f"API Response Status: {response.status_code}")
                return response.json()

            # Handle API-specific error responses
            try:
                error_details = response.json()
            except ValueError:
                error_details = response.text

            # Log the error details
            logger.error(f"API Error: {response.status_code} - {error_details}")

            # Raise a more informative exception
            raise requests.RequestException(
                f"API Error: {response.status_code}, "
                f"Details: {error_details}"
            )

        except requests.RequestException as e:
            # Log the exception
            logger.exception(f"Request failed: {str(e)}")
            raise
        except Exception as e:
            # Catch any unexpected errors
            logger.exception(f"Unexpected error in API request: {str(e)}")
            raise
