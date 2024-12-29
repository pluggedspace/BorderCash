import uuid
from django.db import models
from decimal import Decimal
from app.models import User
from invest.services.utils import fetch_batch_stock_prices


class TradingAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    virtual_balance = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.0"))
    alpaca_tag = models.CharField(max_length=50, unique=True, blank=True)  # Unique tag for Alpaca account
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s Trading Account"

    def save(self, *args, **kwargs):
        """Override save method to generate a unique alpaca_tag if not set"""
        if not self.alpaca_tag:
            self.alpaca_tag = str(uuid.uuid4())  # Generate a unique tag using UUID
        super().save(*args, **kwargs)  # Call the parent class's save method


class PortfolioAllocation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    symbol = models.CharField(max_length=10)
    quantity = models.DecimalField(max_digits=18, decimal_places=6, default=Decimal("0.0"))
    avg_price = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.0"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "symbol"]),
        ]

    def __str__(self):
        return f"{self.symbol} - {self.quantity} shares"


class TransactionHistory(models.Model):
    class TransactionType(models.TextChoices):
        BUY = "buy", "Buy"
        SELL = "sell", "Sell"

    class TransactionStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    symbol = models.CharField(max_length=10)
    transaction_type = models.CharField(max_length=10, choices=TransactionType.choices)
    quantity = models.DecimalField(max_digits=18, decimal_places=6)
    price = models.DecimalField(max_digits=18, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=TransactionStatus.choices,
        default=TransactionStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} {self.symbol} - {self.quantity} shares"


class TradeHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    stock_symbol = models.CharField(max_length=10)
    quantity = models.DecimalField(max_digits=18, decimal_places=6)
    purchase_price = models.DecimalField(max_digits=18, decimal_places=2)
    purchase_timestamp = models.DateTimeField(auto_now_add=True)

    def current_value(self):
        current_price = fetch_batch_stock_prices(self.stock_symbol)
        return current_price * self.quantity

    def profit_or_loss(self):
        current_price = fetch_batch_stock_prices(self.stock_symbol)
        return (current_price - self.purchase_price) * self.quantity
