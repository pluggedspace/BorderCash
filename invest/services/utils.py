import requests
from django.core.cache import cache

from requests.exceptions import RequestException
from swif import settings

# Alpaca API keys (replace with your actual keys)
ALPACA_API_KEY = settings.ALPACA_API_KEY
ALPACA_API_SECRET = settings.ALPACA_SECRET_KEY
ALPACA_BASE_URL = "https://data.alpaca.markets/v2"

# Constants for Alpaca Webhook URL
ALPACA_WEBHOOK_URL = "https://your-swif-backend.com/api/webhook/alpaca/"


def fetch_current_stock_price(symbol):
    """
    Fetch the current stock price for a given symbol using Alpaca's API.

    Args:
        symbol (str): The stock symbol (e.g., 'AAPL').

    Returns:
        float: The current stock price.

    Raises:
        ValueError: If the API response is invalid or data is missing.
        RequestException: If the API request fails.
    """
    url = f"{ALPACA_BASE_URL}/stocks/{symbol}/quotes/latest"
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)  # Added timeout for better error handling
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx, 5xx)
    except RequestException as e:
        raise RequestException(f"Failed to fetch stock price for {symbol}: {e}")

    # Process the response data
    data = response.json()
    if "askprice" in data and data["askprice"] is not None:
        return float(data["askprice"])  # Latest ask price
    else:
        raise ValueError(f"Price data is not available for the symbol {symbol}.")


def fetch_and_cache_stock_price(symbol):
    """
    Fetch the current stock price and cache it for a short period.
    """
    cache_key = f"stock_price_{symbol}"
    cached_price = cache.get(cache_key)
    if cached_price:
        return cached_price

    # Fetch from Alpaca API
    current_price = fetch_current_stock_price(symbol)

    # Cache for 5 minutes (300 seconds)
    cache.set(cache_key, current_price, timeout=300)
    return current_price


def fetch_batch_stock_prices(symbols):
    """
    Fetch current prices for multiple stock symbols.

    Args:
        symbols (list): List of stock symbols (e.g., ['AAPL', 'GOOG']).

    Returns:
        dict: A dictionary with symbols as keys and their respective prices as values.

    Raises:
        RequestException: If the API request fails.
    """
    url = f"{ALPACA_BASE_URL}/stocks/quotes/latest"
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
    }
    params = {"symbols": ",".join(symbols)}

    try:
        response = requests.get(url, headers=headers, params=params,
                                timeout=10)  # Added timeout for better error handling
        response.raise_for_status()
    except RequestException as e:
        raise RequestException(f"Failed to fetch stock prices for symbols {symbols}: {e}")

    data = response.json()
    return {symbol: quote.get("askprice", None) for symbol, quote in data.items()}


def register_webhook():
    """Register Alpaca webhook endpoint."""
    url = "https://paper-api.alpaca.markets/v2/webhooks"
    payload = {
        "url": ALPACA_WEBHOOK_URL,
        "event_types": ["trade_updates"],
    }
    headers = {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_API_SECRET,
    }

    try:
        response = requests.post(url, json=payload, headers=headers,
                                 timeout=10)  # Added timeout for better error handling
        response.raise_for_status()
    except RequestException as e:
        raise RequestException(f"Failed to register webhook: {e}")

    return response.json()
