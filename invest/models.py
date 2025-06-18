import requests
from decimal import Decimal
from django.db import models
from django.contrib.auth import get_user_model
from app.models import USDAccount
from django.utils import timezone
from .services.stellar_utils import StellarService

User = get_user_model()
STELLAR_HORIZON_URL = "https://horizon.stellar.org"



class TokenizedStock(models.Model):
    """Stores tokenized stock data with historical prices."""
    symbol = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=12, decimal_places=6, blank=True, null=True)
    price_in_xlm = models.DecimalField(max_digits=12, decimal_places=6, blank=True, null=True)
    issuer_address = models.CharField(max_length=255, blank=True, null=True)
    historical_prices = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    last_updated = models.DateTimeField(auto_now=True)

    def update_price(self):
        """Update price using StellarService."""
        prices = StellarService.fetch_stellar_prices(self.symbol, self.issuer_address)
        if prices:
            self.price_in_xlm = prices['price_xlm']
            self.price = prices['price_usd']
            
            timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
            if not isinstance(self.historical_prices, dict):
                self.historical_prices = {}
                
            self.historical_prices[timestamp] = {
                'usd': str(self.price),
                'xlm': str(self.price_in_xlm)
            }
            self.save()

class UserInvestment(models.Model):
    """Tracks user holdings and manages auto-sell thresholds."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    stock = models.ForeignKey(TokenizedStock, on_delete=models.CASCADE)
    amount_held = models.DecimalField(max_digits=12, decimal_places=4, default=0.0000)
    purchase_price = models.DecimalField(max_digits=12, decimal_places=2)
    current_value = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    unrealized_profit_loss = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    # Auto-sell thresholds
    stop_loss_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    take_profit_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    def update_value(self):
        """Updates investment value and checks for auto-sell conditions."""
        if self.stock.price is not None:
            self.current_value = self.amount_held * self.stock.price
            self.unrealized_profit_loss = self.current_value - (self.amount_held * self.purchase_price)
        else:
            self.current_value = 0.00
            self.unrealized_profit_loss = 0.00
    
        self.save()

    class Meta:
        indexes = [
            models.Index(fields=['user', 'amount_held']),
            models.Index(fields=['stop_loss_price']),
            models.Index(fields=['take_profit_price']),
        ]

class InvestmentAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)

class TransactionLog(models.Model):
    """ Records all buy and sell transactions. """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    stock = models.ForeignKey(TokenizedStock, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=4, choices=[('BUY', 'Buy'), ('SELL', 'Sell')])
    amount = models.DecimalField(max_digits=12, decimal_places=4)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} {self.transaction_type} {self.stock.symbol} - {self.amount}"



