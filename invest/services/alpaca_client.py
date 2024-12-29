import logging
import requests
from alpaca.broker.client import BrokerClient
from django.conf import settings
from invest.models import TradingAccount

# Configure logging
logger = logging.getLogger(__name__)


class AlpacaClient:
    BASE_URL = "https://broker-api.sandbox.alpaca.markets"

    def __init__(self):
        try:
            self.api_key = settings.ALPACA_API_KEY
            self.secret_key = settings.ALPACA_SECRET_KEY

            if not self.api_key or not self.secret_key:
                raise ValueError("Missing Alpaca API credentials in settings.")

            # Initialize BrokerClient with Alpaca API credentials
            self.client = BrokerClient(api_key=self.api_key, secret_key=self.secret_key)
            self.platform_account = "ALPACA"  # Set as a constant or configurable value

        except KeyError as e:
            logger.error(f"Missing Alpaca API credentials in settings: {e}")
            raise
        except ValueError as e:
            logger.error(f"Configuration error: {e}")
            raise

    def _headers(self):
        """Generate headers for authentication."""
        return {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
        }

    def _handle_response(self, response):
        """Handle API response and raise exceptions for errors."""
        if not response.ok:
            error_message = response.json().get("message", "Unknown error")
            logger.error(f"Alpaca API Error: {error_message}")
            raise Exception(f"Alpaca API Error: {error_message}")
        return response.json()

    def place_order(self, symbol, qty, side, alpaca_tag):
        """Place an order on Alpaca with a sub-tag for user identification."""
        url = f"{self.BASE_URL}/v2/orders"
        headers = self._headers()

        order_data = {
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "type": "market",  # You can adjust this to your order type
            "time_in_force": "gtc",  # Good-Til-Canceled
            "tags": [alpaca_tag]  # Using sub_tag (which is essentially alpaca_tag)
        }

        try:
            response = requests.post(url, json=order_data, headers=headers)
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error placing order: {e}")
            return {"error": f"Error placing order: {e}"}

    def get_account(self):
        """Fetch account details from Alpaca."""
        url = f"{self.BASE_URL}/account"
        try:
            response = requests.get(url, headers=self._headers())
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching account: {e}")
            raise

    def get_positions(self):
        """Fetch current positions from Alpaca."""
        url = f"{self.BASE_URL}/positions"
        try:
            response = requests.get(url, headers=self._headers())
            return self._handle_response(response)
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching positions: {e}")
            raise

    def get_sub_tag(self, user):
        """Fetch the sub_tag (which is the alpaca_tag) for the user from the TradingAccount model."""
        try:
            trading_account = TradingAccount.objects.get(user=user)
            return trading_account.alpaca_tag  # Return alpaca_tag as sub_tag
        except TradingAccount.DoesNotExist:
            logger.error(f"TradingAccount not found for user: {user}")
            return None
