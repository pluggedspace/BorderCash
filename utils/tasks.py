from celery import shared_task
from .models import Order
from .shop_service import fetch_amazon_order_status, fetch_aliexpress_order_status


@shared_task
def update_order_status():
    pending_orders = Order.objects.filter(order_status__in=["Pending", "Processing"])
    for order in pending_orders:
        fetch_amazon_order_status(order)
        fetch_aliexpress_order_status(order)
