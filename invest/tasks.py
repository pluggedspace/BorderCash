from celery import shared_task
from django.core.cache import cache

from invest.services.alpaca_client import AlpacaClient
from .models import PortfolioAllocation, TradingAccount, TradeHistory
from invest.services.utils import fetch_batch_stock_prices

alpaca_api = AlpacaClient


@shared_task
def sync_portfolio():
    """Sync Alpaca positions with PortfolioAllocation."""
    positions = alpaca_api.get_positions()

    for position in positions:
        symbol = position["symbol"]
        qty = float(position["qty"])
        avg_price = float(position["avg_entry_price"])

        # Update PortfolioAllocation for all users proportionately
        total_virtual_balance = sum(account.virtual_balance for account in TradingAccount.objects.all())
        for account in TradingAccount.objects.all():
            user_ratio = account.virtual_balance / total_virtual_balance if total_virtual_balance > 0 else 0

            allocation, created = PortfolioAllocation.objects.get_or_create(
                user=account.user,
                symbol=symbol,
                defaults={"quantity": 0.0, "avg_price": 0.0},
            )

            allocation.quantity = qty * user_ratio
            allocation.avg_price = avg_price  # Adjusted average price
            allocation.save()


@shared_task
def sync_account_balance():
    """Sync Alpaca omnibus account balance with TradingAccount."""
    account_info = alpaca_api.get_account()
    omnibus_balance = float(account_info["cash"])

    # Distribute omnibus balance proportionately across user accounts
    total_virtual_balance = sum(account.virtual_balance for account in TradingAccount.objects.all())

    for account in TradingAccount.objects.all():
        user_ratio = account.virtual_balance / total_virtual_balance if total_virtual_balance > 0 else 0
        account.virtual_balance = omnibus_balance * user_ratio
        account.save()


@shared_task
def update_stock_prices():
    symbols = TradeHistory.objects.values_list("stock_symbol", flat=True).distinct()
    prices = fetch_batch_stock_prices(symbols)
    for symbol, price in prices.items():
        cache.set(f"stock_price_{symbol}", price, timeout=300)
