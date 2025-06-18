from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Transaction, Notification, UserPoints, Referral 
from django.utils import timezone
from decimal import Decimal
from django.contrib.auth.signals import user_logged_in
from django.contrib.sites.models import Site
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from .utils.mail import send_email


from django.contrib.auth import get_user_model

User = get_user_model()

# Notification
@receiver(post_save, sender=Transaction)
def create_notification(sender, instance, created, **kwargs):
    if instance.status in ['completed', 'failed']:
        if instance.status == 'completed':
            title = "Transaction Successful"
            message = (
                f"Your {instance.transaction_type} of {instance.currency} {instance.amount} "
                f"has been successfully processed."
            )
        elif instance.status == 'failed':
            title = "Transaction Failed"
            message = (
                f"Your {instance.transaction_type} of {instance.currency} {instance.amount} "
                f"failed. Reason: {instance.error_message or 'Unknown error.'}"
            )

        Notification.objects.create(
            user=instance.user,
            title=title,
            message=message,
            type='transaction',
            created_at=timezone.now()  # Fix: Use timezone.now()
        )



# Define points for each transaction type
TRANSACTION_POINTS = {
    'deposit': 1.5,
    'withdraw': 1,
    'transfer': 0.5,
    'commission': 2.0
}

REGISTRATION_BONUS = 20

REFERRAL_POINTS = 10

@receiver(post_save, sender=Transaction)
def award_points(sender, instance, **kwargs):
    """ Awards points when a transaction is completed """
    if instance.status == "completed":
        user_points, _ = UserPoints.objects.get_or_create(user=instance.user)
        points = TRANSACTION_POINTS.get(instance.transaction_type, 0)

        if points > 0:
            success = user_points.add_points(Decimal(points), f"Transaction: {instance.transaction_type}")
            if not success:
                print(f"User {instance.user} reached daily/weekly points limit.")

@receiver(post_save, sender=User)
def award_registration_points(sender, instance, created, **kwargs):
    """
    Awards points to a user when they register for the first time.
    """
    if created:  # Ensures this runs only for new users
        user_points, _ = UserPoints.objects.get_or_create(user=instance)
        user_points.points += Decimal(REGISTRATION_BONUS)
        user_points.save()

@receiver(post_save, sender=Referral)
def award_referral_points(sender, instance, created, **kwargs):
    """
    Awards points when a referral is approved
    """
    if instance.status == 'approved' and not instance.approved_at:
        # Ensure we only process this once
        instance.approved_at = timezone.now()
        instance.save(update_fields=['approved_at'])
        
        referrer_points, _ = UserPoints.objects.get_or_create(
            user=instance.referrer
        )
        success = referrer_points.add_points(
            Decimal(REFERRAL_POINTS),
            f"Referral bonus for {instance.referred_user}"
        )
        
        if not success:
            print(f"Referrer {instance.referrer} reached daily/weekly points limit.")

"""
# Email
@receiver(post_save, sender=Transaction)
def send_transaction_email(sender, instance, **kwargs):
    #Send email notification when a transaction is completed or failed.

    email_context = {
        "user": instance.user,
        "transaction_type": instance.get_transaction_type_display(),
        "transaction_id": instance.transaction_id or "N/A",
        "amount": f"{instance.amount} {instance.currency}",
        "fee": f"{instance.fee_amount} {instance.currency}",
        "payment_method": instance.payment_method,
        "status": instance.get_status_display(),
        "timestamp": instance.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "description": instance.description or "No description provided",
    }

    if instance.status == "completed":
        subject = f"Transaction {instance.get_transaction_type_display()} Successful"
        template = "transaction_success_email"
    elif instance.status == "failed":
        subject = f"Transaction {instance.get_transaction_type_display()} Failed"
        template = "transaction_failed_email"
        email_context["error_message"] = instance.error_message or "No error details available."

    else:
        return  # Do nothing for other statuses

    send_email(
        recipient=instance.user.email,
        subject=subject,
        template_name=template,
        context=email_context
    )


@receiver(post_save, sender=User)
def send_welcome_email(sender, instance, created, **kwargs):
    #Send a welcome email when a user registers.
    if created:
        send_email(
            subject="Welcome to BorderCash!",
            recipient=instance.email,
            template_name="welcome_email",
            context={
                "username": instance.username,
                "subject": "Welcome to BorderCash!"  # Added subject to context for template use
            }
        )

@receiver(user_logged_in)
def send_login_notification(sender, request, user, **kwargs):
    #Send an email when a user logs in.
    subject = "Login Alert"
    context = {
        "username": user.username,
        "ip": request.META.get("REMOTE_ADDR"),
    }
    send_email(
        subject="Login Alert",
        recipient=user.email,
        template_name="login_alert",
        context=context
    )


def send_password_reset_email(user):
    #Send password reset email when requested.
    current_site = Site.objects.get_current()
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_url = f"https://{current_site.domain}{reverse('password_reset_confirm', args=[uid, token])}"

    send_email(
        subject="Password Reset Request",
        recipient=user.email,
        template_name="password_reset",
        context={
            "username": user.username,
            "reset_url": reset_url
        }
    )

"""