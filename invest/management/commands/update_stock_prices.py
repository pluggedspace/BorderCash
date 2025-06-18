from django.core.management.base import BaseCommand
from django.utils import timezone
from invest.services.stellar_utils import stellar_service
import logging
import time
from decimal import Decimal

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Update prices for all active tokenized stocks from the Stellar network'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed update information',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update all prices even if they haven\'t changed significantly',
        )

    def handle(self, *args, **options):
        verbose = options['verbose']
        force_update = options['force']
        start_time = time.time()
        
        self.stdout.write(f"{timezone.now()} - Starting stock price update...")
        if force_update:
            self.stdout.write(self.style.WARNING("Forcing update of all prices"))
        
        try:
            from invest.models import TokenizedStock
            stocks = TokenizedStock.objects.filter(is_active=True)
            self.stdout.write(f"Found {len(stocks)} active stocks to update")
            
            updated_count = 0
            price_errors = 0
            unchanged_count = 0
            
            for stock in stocks:
                try:
                    if verbose:
                        self.stdout.write(f"\nFetching prices for {stock.symbol}...")
                    
                    prices = stellar_service.fetch_stellar_prices(stock.symbol, stock.issuer_address)
                    
                    if not prices:
                        price_errors += 1
                        self.stdout.write(
                            self.style.WARNING(f"  Could not fetch prices for {stock.symbol}")
                        )
                        continue
                    
                    # Log the fetched prices
                    if verbose:
                        self.stdout.write(f"  Fetched prices for {stock.symbol}:")
                        self.stdout.write(f"    USD: {prices['price_usd']:.6f}")
                        self.stdout.write(f"    XLM: {prices['price_xlm']:.6f}")
                        self.stdout.write(f"    XLM/USD: {prices['xlm_usd_rate']:.6f}")
                    
                    # Check if price changed significantly (0.01% threshold)
                    price_changed = (
                        abs(prices['price_usd'] - stock.price) / stock.price > Decimal('0.0001') or 
                        abs(prices['price_xlm'] - stock.price_in_xlm) / stock.price_in_xlm > Decimal('0.0001')
                    )
                    
                    if price_changed or force_update:
                        old_usd = stock.price
                        old_xlm = stock.price_in_xlm
                        
                        stock.price = prices['price_usd']
                        stock.price_in_xlm = prices['price_xlm']
                        stock.save()
                        updated_count += 1
                        
                        if verbose:
                            self.stdout.write(self.style.SUCCESS(f"  Updated {stock.symbol}:"))
                            self.stdout.write(f"    USD: {old_usd:.6f} → {stock.price:.6f}")
                            self.stdout.write(f"    XLM: {old_xlm:.6f} → {stock.price_in_xlm:.6f}")
                    else:
                        unchanged_count += 1
                        if verbose:
                            self.stdout.write(f"  No significant change for {stock.symbol}")
                
                except Exception as e:
                    price_errors += 1
                    error_msg = f"Error processing {stock.symbol}: {str(e)}"
                    self.stdout.write(self.style.ERROR(error_msg))
                    logger.error(error_msg, exc_info=True)
                    continue
            
            elapsed_time = time.time() - start_time
            summary_msg = (
                f"\nUpdate completed in {elapsed_time:.2f} seconds\n"
                f"Stocks processed: {len(stocks)}\n"
                f"Successfully updated: {updated_count}\n"
                f"Unchanged: {unchanged_count}\n"
                f"Errors: {price_errors}"
            )
            
            self.stdout.write(summary_msg)
            logger.info(summary_msg)
            
            if price_errors > 0:
                self.stdout.write(self.style.WARNING(f"Encountered {price_errors} errors during update"))
            
        except Exception as e:
            error_msg = f"Failed to update stock prices: {str(e)}"
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg, exc_info=True)
            raise