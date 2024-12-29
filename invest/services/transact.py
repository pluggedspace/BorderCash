import requests
from django.conf import settings

from invest.models import TradingAccount


# Funds deposit
def deposit_funds(user, amount):
    """Handle user deposits."""
    # Update user's virtual balance
    account = TradingAccount.objects.get(user=user)
    account.virtual_balance += amount
    account.save()

    # (Optional) Notify Alpaca if real funds are deposited to the omnibus account
    # You can use your payment gateway's webhook here


# Withdrawing funds
def withdraw_funds(user, amount):
    """Handle user withdrawals."""
    account = TradingAccount.objects.get(user=user)

    # Check user's balance
    if account.virtual_balance < amount:
        raise ValueError("Insufficient balance")

    # Deduct from user's virtual balance
    account.virtual_balance -= amount
    account.save()

    # Notify Alpaca or payment gateway to process the withdrawal
    # Example: Convert omnibus cash to USDC for user withdrawal

