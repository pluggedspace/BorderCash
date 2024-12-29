from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import TransactionHistory


@receiver(post_save, sender=TransactionHistory)
def notify_user_trade(sender, instance, created, **kwargs):
    if created:
        user = instance.user
        # Send notification (e.g., email, in-app notification)
        message = f"Your {instance.transaction_type} order for {instance.symbol} was {instance.status}."
        print(f"Notify {user.email}: {message}")


@receiver(post_save, sender=TransactionHistory)
def send_trade_notification(sender, instance, created, **kwargs):
    if created and instance.status == "completed":
        subject = "Trade Completed"
        message = f"Your {instance.transaction_type} order for {instance.symbol} is complete."
        send_mail(subject, message, "no-reply@swif.com", [instance.user.email])
