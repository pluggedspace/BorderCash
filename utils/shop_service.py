import requests
from django.core.mail import send_mail
from firebase_admin import messaging


def place_amazon_order(order):
    api_url = "https://api.amazon.com/orders"  # Example endpoint
    headers = {"Authorization": "Bearer <your-access-token>"}
    payload = {
        "product_id": order.product.id,
        "quantity": order.quantity,
        "shipping_address": order.user.shipping_address,
    }
    response = requests.post(api_url, json=payload, headers=headers)
    return response.json()


def fetch_amazon_order_status(order):
    api_url = f"https://api.amazon.com/orders/{order.tracking_number}/status"  # Example endpoint
    headers = {"Authorization": "Bearer <your-access-token>"}
    response = requests.get(api_url, headers=headers)

    if response.status_code == 200:
        order_status = response.json().get("status")
        order.order_status = order_status
        order.save()
    return order_status


def place_aliexpress_order(order):
    api_url = "https://api.amazon.com/orders"  # Example endpoint
    headers = {"Authorization": "Bearer <your-access-token>"}
    payload = {
        "product_id": order.product.id,
        "quantity": order.quantity,
        "shipping_address": order.user.shipping_address,
    }
    response = requests.post(api_url, json=payload, headers=headers)
    return response.json()


def fetch_aliexpress_order_status(order):
    api_url = f"https://api.amazon.com/orders/{order.tracking_number}/status"  # Example endpoint
    headers = {"Authorization": "Bearer <your-access-token>"}
    response = requests.get(api_url, headers=headers)

    if response.status_code == 200:
        order_status = response.json().get("status")
        order.order_status = order_status
        order.save()
    return order_status


def send_order_confirmation(user, order):
    subject = f"Order Confirmation - {order.id}"
    message = f"Dear {user.username},\n\nYour order for {order.product.name} has been placed successfully.\n\nTotal: ${order.total_cost}\nStatus: {order.order_status}\n\nThank you for using Swif!"
    send_mail(subject, message, "noreply@swif.com", [user.email])


def send_push_notification(user, message):
    registration_token = user.device_token  # Assuming users register their device tokens
    notification = messaging.Message(
        notification=messaging.Notification(
            title="Order Update",
            body=message,
        ),
        token=registration_token,
    )
    messaging.send(notification)
