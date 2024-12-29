from django.db import models
from app.models import User


class Product(models.Model):
    name = models.CharField(max_length=255)
    platform = models.CharField(max_length=50)  # e.g., "Amazon", "AliExpress"
    product_url = models.URLField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="USD")  # e.g., "USD"
    variations = models.JSONField(blank=True, null=True)  # e.g., {"size": "M", "color": "Red"}

    def __str__(self):
        return f"{self.name} ({self.platform})"


class Order(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    payment_status = models.CharField(max_length=50, default="Pending")  # e.g., "Pending", "Completed"
    tracking_info = models.JSONField(blank=True, null=True)
    tracking_number = models.CharField(max_length=100, blank=True, null=True)
    order_status = models.CharField(
        max_length=50,
        choices=[
            ("Pending", "Pending"),
            ("Processing", "Processing"),
            ("Shipped", "Shipped"),
            ("Delivered", "Delivered"),
            ("Cancelled", "Cancelled"),
        ],
        default="Pending",
    )

    def __str__(self):
        return f"Order {self.id} by {self.user.username}"


class ShoppingFee(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    platform_fee = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_fee = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Fees for Order {self.order.id}"
