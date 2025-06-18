from django.core.cache import cache
from app.models import ExchangeRate
from app.tasks import update_exchange_rates
import logging
from decimal import Decimal, InvalidOperation

# Set up logger
logger = logging.getLogger(__name__)

def convert_usd_to_local(usd_amount, currency_code):
    """
    Convert USD amount to local currency and return both converted amount and exchange rate.
    Handles caching, logging, and type conversion between Decimal and float.
    
    Args:
        usd_amount (Decimal): Amount in USD to convert
        currency_code (str): Target currency code
        
    Returns:
        tuple: (converted_amount, exchange_rate) both as Decimal
    """
    # Validate input types
    if not isinstance(usd_amount, Decimal):
        try:
            usd_amount = Decimal(str(usd_amount))
        except (InvalidOperation, TypeError) as e:
            logger.error(f"Invalid usd_amount: {usd_amount}. Error: {str(e)}")
            raise ValueError("usd_amount must be convertible to Decimal")

    currency_code = currency_code.upper()
    cache_key = f'exchange_rate_{currency_code}'
    
    # Try to get exchange rate from cache first
    exchange_rate = cache.get(cache_key)
    
    if exchange_rate is None:
        # Cache miss, fetch exchange rates
        try:
            # Trigger async update (fire and forget)
            update_exchange_rates.delay()
            
            # Get the current rate from DB
            exchange_rate = ExchangeRate.objects.get(currency_code=currency_code)
            
            # Store in cache for 1 hour
            cache.set(cache_key, exchange_rate, timeout=3600)
            logger.info(f"Cache miss for {currency_code}, fetched from DB.")
        except ExchangeRate.DoesNotExist:
            logger.warning(f"Exchange rate for {currency_code} not found. Using default rate.")
            return usd_amount, Decimal('1.0')
        except Exception as e:
            logger.error(f"Error fetching exchange rate for {currency_code}: {str(e)}")
            return usd_amount, Decimal('1.0')
    
    try:
        # Ensure rate is Decimal for consistent arithmetic
        rate_to_usd = Decimal(str(exchange_rate.rate_to_usd))
        
        logger.info(f"Converting {usd_amount} USD to {currency_code} at rate {rate_to_usd}.")
        
        # Convert USD to local currency
        local_amount = round(usd_amount * rate_to_usd, 2)
        return local_amount, rate_to_usd
    except Exception as e:
        logger.error(f"Conversion error for {usd_amount} USD to {currency_code}: {str(e)}")
        return usd_amount, Decimal('1.0')