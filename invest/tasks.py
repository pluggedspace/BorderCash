import logging
from decimal import Decimal
from django.db import transaction
from django.contrib.auth import get_user_model
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from stellar_sdk.exceptions import NotFoundError, BadResponseError
from invest.models import UserInvestment, TokenizedStock, TransactionLog, InvestmentAccount
from app.models import Notification
from .services.stellar_utils import stellar_service
import requests 


from stellar_sdk import Server, Keypair, TransactionBuilder, Network, Asset
from django.conf import settings
import decimal

User = get_user_model()
logger = logging.getLogger(__name__)

# ======================
# CORE TRADING FUNCTIONS
# ======================

@shared_task(bind=True, max_retries=3)
def process_trade(self, user_id, transaction_type, asset_symbol, amount, **kwargs):
    """Centralized trade processor with enhanced error handling"""
    try:
        # Validate inputs
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Amount must be positive")

        user = User.objects.get(id=user_id)
        stock = TokenizedStock.objects.get(symbol=asset_symbol)
        current_price = Decimal(stock.price)

        if transaction_type.upper() == "BUY":
            return process_custodian_buy(user, stock, amount, current_price, kwargs)
        elif transaction_type.upper() == "SELL":
            if kwargs.get('auto_triggered'):
                return process_auto_sell(user, stock, amount, current_price, kwargs)
            return process_custodian_sell(user, stock, amount, current_price)
        else:
            raise ValueError("Invalid transaction type")

    except MaxRetriesExceededError:
        logger.critical(f"Permanent trade failure for user {user_id}")
        notify_admin(f"Trade failed after retries: {asset_symbol} {amount}")
    except Exception as e:
        logger.error(f"Trade processing error: {str(e)}")
        self.retry(exc=e, countdown=60)

# ======================
# AUTOMATED PROCESSING
# ======================

@shared_task
def auto_process_stocks():
    """Main automated trading engine"""
    users = User.objects.filter(
        investmentaccount__isnull=False
    ).prefetch_related('userinvestment_set').distinct()
    
    for user in users:
        try:
            process_user_investments(user)
        except Exception as e:
            logger.error(f"User {user.id} processing failed: {str(e)}")
            continue

def process_user_investments(user):
    """Process all investments for a single user"""
    
    investments = UserInvestment.objects.filter(
        user=user,
        amount_held__gt=0,
    ).exclude(
        stop_loss_price__isnull=True,
        take_profit_price__isnull=True
    ).select_related('stock')
    
    for inv in investments:
        if needs_processing(inv):  # This check is still needed for price comparisons
            trigger_auto_trade(inv)

def needs_processing(investment):
    """Determine if investment meets auto-trade criteria"""
    current_price = Decimal(investment.stock.price)
    
    stop_loss_triggered = (
        investment.stop_loss_price is not None and  # Check if set
        current_price <= investment.stop_loss_price  # Check if price hit stop-loss
    )
    
    take_profit_triggered = (
        investment.take_profit_price is not None and  # Check if set
        current_price >= investment.take_profit_price  # Check if price hit take-profit
    )
    
    return stop_loss_triggered or take_profit_triggered

def trigger_auto_trade(investment):
    """Initiate automated trade with proper parameters"""
    stock = investment.stock
    current_price = Decimal(stock.price)
    
    trigger_type = (
        "stop-loss" if (
            investment.stop_loss_price is not None and 
            current_price <= investment.stop_loss_price
        )
        else "take-profit"
    )
    
    process_trade.delay(
        user_id=investment.user.id,
        transaction_type="sell",
        asset_symbol=stock.symbol,
        amount=investment.amount_held,
        auto_triggered=True,
        trigger_type=trigger_type,
        trigger_price=str(current_price)
    )
    
# ======================
# TRADE IMPLEMENTATIONS
# ======================

def process_custodian_buy(user, stock, amount, price, order_params):
    """Handle custodian-based buy operations"""
    total_cost = amount * price
    
    with transaction.atomic():
        account = InvestmentAccount.objects.select_for_update().get(user=user)
        if account.balance < total_cost:
            raise ValueError(f"Insufficient funds. Need {total_cost}, have {account.balance}")

        result = stellar_service.execute_trade(
            transaction_type="buy",
            asset_symbol=stock.symbol,
            amount=amount,
            stop_loss=order_params.get('stop_loss'),
            take_profit=order_params.get('take_profit')
        )

        if result['status'] != 'success':
            raise ValueError(result.get('error', 'Stellar trade failed'))

        account.balance -= total_cost
        account.save()

        UserInvestment.objects.create(
            user=user,
            stock=stock,
            amount_held=amount,
            entry_price=price,
            stop_loss=Decimal(order_params.get('stop_loss')) if order_params.get('stop_loss') else None,
            take_profit=Decimal(order_params.get('take_profit')) if order_params.get('take_profit') else None,
            stellar_tx_hash=result['tx_hash']
        )

        create_transaction_log(
            user=user,
            stock=stock,
            transaction_type="BUY",
            amount=amount,
            price=price,
            tx_hash=result['tx_hash'],
            notes=order_params.get('notes')
        )

        send_notification(user, f"Bought {amount} {stock.symbol} at {price}")
        
        return {'status': 'success', 'tx_hash': result['tx_hash']}

def process_custodian_sell(user, stock, amount, price):
    """Handle manual sell operations"""
    total_value = amount * price
    
    with transaction.atomic():
        investments = UserInvestment.objects.filter(
            user=user,
            stock=stock,
            amount_held__gt=0
        ).select_for_update().order_by('purchase_date')

        total_available = sum(inv.amount_held for inv in investments)
        if total_available < amount:
            raise ValueError(f"Insufficient shares. Need {amount}, have {total_available}")

        result = stellar_service.execute_trade(
            transaction_type="sell",
            asset_symbol=stock.symbol,
            amount=amount
        )

        if result['status'] != 'success':
            raise ValueError(result.get('error', 'Stellar trade failed'))

        account = InvestmentAccount.objects.select_for_update().get(user=user)
        account.balance += total_value
        account.save()

        process_fifo_sale(investments, amount)

        create_transaction_log(
            user=user,
            stock=stock,
            transaction_type="SELL",
            amount=amount,
            price=price,
            tx_hash=result['tx_hash']
        )

        send_notification(user, f"Sold {amount} {stock.symbol} at {price}")
        
        return {'status': 'success', 'tx_hash': result['tx_hash']}

def process_auto_sell(user, stock, amount, price, params):
    """Specialized handler for automated sales"""
    result = stellar_service.execute_trade(
        transaction_type="sell",
        asset_symbol=stock.symbol,
        amount=amount
    )
    
    if result['status'] != 'success':
        raise ValueError(result.get('error', 'Auto-trade failed'))

    with transaction.atomic():
        account = InvestmentAccount.objects.select_for_update().get(user=user)
        account.balance += amount * price
        account.save()

        investments = UserInvestment.objects.filter(
            user=user,
            stock=stock,
            amount_held__gt=0
        ).select_for_update().order_by('purchase_date')

        process_fifo_sale(investments, amount)

        create_transaction_log(
            user=user,
            stock=stock,
            transaction_type="SELL",
            amount=amount,
            price=price,
            tx_hash=result['tx_hash'],
            notes=f"Auto-sell: {params.get('trigger_type')} at {price}"
        )

        send_notification(
            user,
            f"Auto-sell: {params.get('trigger_type')} triggered for {stock.symbol}"
        )
        
        return {'status': 'success', 'tx_hash': result['tx_hash']}

# ======================
# HELPER FUNCTIONS
# ======================

def process_fifo_sale(investments, amount):
    """Process FIFO sale allocation"""
    remaining = amount
    for inv in investments:
        if remaining <= 0:
            break
        
        sell_amount = min(remaining, inv.amount_held)
        inv.amount_held -= sell_amount
        remaining -= sell_amount
        
        if inv.amount_held <= 0:
            inv.delete()
        else:
            inv.save()

def create_transaction_log(user, stock, transaction_type, amount, price, tx_hash, notes=None):
    """Standardized transaction recording"""
    TransactionLog.objects.create(
        user=user,
        stock=stock,
        transaction_type=transaction_type,
        amount=amount,
        price=price,
        status="completed",
        stellar_tx_hash=tx_hash,
        notes=notes
    )

def send_notification(user, message):
    """Standardized notification system"""
    Notification.objects.create(user=user, message=message)
    logger.info(f"Notification sent to {user.username}")

def notify_admin(message):
    """Critical error notification"""
    admin = User.objects.filter(is_superuser=True).first()
    if admin:
        Notification.objects.create(user=admin, message=f"ADMIN ALERT: {message}")
        logger.critical(f"Admin notified: {message}")

# ======================
# SUPPORTING TASKS
# ======================

@shared_task
def update_tokenized_stock_prices():
    """Market data updater with enhanced error handling"""
    try:
        updated = stellar_service.update_stock_prices()
        logger.info(f"Updated {updated} stock prices")
        return updated
    except Exception as e:
        logger.error(f"Price update failed: {str(e)}")
        raise update_tokenized_stock_prices.retry(exc=e, countdown=300)
        
        
        
# tasks/stellar_transfer.py



@shared_task
def transfer_usdc_between_custodies(amount: str, direction: str):
    """
    Transfers USDC between centralized custody and investment pool on Stellar mainnet.

    Args:
        amount (str): The amount to transfer
        direction (str): 'to_investment' or 'to_central'

    Returns:
        dict: Result of transaction submission
    """
    try:
        decimal_amount = decimal.Decimal(amount)
        if decimal_amount <= 0:
            raise ValueError("Amount must be greater than zero.")

        server = Server("https://horizon.stellar.org")
        network_passphrase = Network.PUBLIC_NETWORK_PASSPHRASE

        # Load keys based on direction
        if direction == "to_investment":
            source_secret = settings.STELLAR_PLATFORM_SECRET
            destination_public = settings.INVESTMENT_POOL_PUBLIC
        elif direction == "to_central":
            source_secret = settings.INVESTMENT_ACCOUNT_SECRET
            destination_public = settings.CENTRAL_CUSTODY_PUBLIC
        else:
            raise ValueError("Invalid direction. Use 'to_investment' or 'to_central'.")

        source_keypair = Keypair.from_secret(source_secret)
        source_public = source_keypair.public_key

        source_account = server.load_account(account_id=source_public)

        usdc = Asset("USDC", settings.USDC_ISSUER_PUBLIC_KEY)

        tx = (
            TransactionBuilder(
                source_account=source_account,
                network_passphrase=network_passphrase,
                base_fee=100,
            )
            .append_payment_op(destination=destination_public, amount=str(decimal_amount), asset=usdc)
            .set_timeout(30)
            .build()
        )

        tx.sign(source_keypair)
        response = server.submit_transaction(tx)

        return {
            "status": "success",
            "tx_hash": response.get("hash"),
            "ledger": response.get("ledger"),
            "amount": str(amount),
            "from": source_public,
            "to": destination_public
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}
        
        