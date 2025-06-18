# Standard library
import logging
import random
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

# Third-party
import requests
from rest_framework.exceptions import ValidationError

# Django core
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.html import format_html
from django.utils.timezone import now, timedelta
from django.utils import timezone
from datetime import timedelta
import secrets

logger = logging.getLogger(__name__)

TRANSACTION_TYPES = (
    ('deposit', 'Deposit'),
    ('withdrawal', 'Withdrawal'),
    ('transfer', 'Transfer'),

    ('top-up', 'Top-up'),
    ('bundle', 'Bundle'),
    ('data-bundle', 'Data_bundle'), 
    ('combo-product', 'Combo_product'),

    ('utility_payment', 'Utility_payment'),
    ('gift_card', 'Gift card'),
    ('shopping', 'Shopping')
)

def generate_unique_id():
    return str(uuid.uuid4())[:6]

class Region(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name  # No parentheses

class User(AbstractUser):
    email = models.EmailField(unique=True)
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(null=True, max_length=100, blank=True)
    verification_token_expires = models.DateTimeField(null=True, blank=True)
    referral_code = models.CharField(max_length=20, unique=True, blank=True)
    
    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_set',
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )

    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_permissions_set',
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )
    is_verified = models.BooleanField(default=False)
    
    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self.generate_referral_code()
        super().save(*args, **kwargs)
    
    def generate_referral_code(self):
        return f"{self.username[:3]}{random.randint(1000,9999)}".upper()

    def generate_verification_token(self):
        """Generate and save a new verification token"""
        self.email_verification_token = secrets.token_urlsafe(32)
        self.verification_token_expires = timezone.now() + timedelta(hours=24)
        self.save()
        return self.email_verification_token
    
    def clear_verification_token(self):
        """Clear verification token after successful verification"""
        self.email_verification_token = None
        self.verification_token_expires = None
        self.is_verified = True
        self.save()  
   

    def verify_email(self, token):
        """Verify email using token"""
        if (self.email_verification_token == token and 
            self.verification_token_expires > datetime.now()):
            self.email_verified = True
            self.email_verification_token = ''
            self.save()
            return True
        return False

    def generate_order_id(self) -> str:
        """Generate a unique order ID for Transak"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"ORDER-{self.id}-{timestamp}"

    def __str__(self):
        return self.username        
 
class UserProfile(models.Model):
    # Core user data
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    username = models.CharField(max_length=20, unique=True)
    unique_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    # Basic profile info
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15)
    city = models.CharField(max_length=30)
    state = models.CharField(max_length=30)
    country = models.CharField(max_length=30)
    region = models.ForeignKey(Region, null=True, blank=True, on_delete=models.CASCADE)
    date_of_birth = models.DateField(null=True, blank=True)

    transaction_pin = models.CharField(max_length=128, null=True, blank=True)
    preferred_currency = models.CharField(max_length=3, default='USD')  # or null=True

    @property
    def email(self):
        """Expose email from the User model"""
        return self.user.email

    # KYC-related properties
    @property
    def kyc_status(self):
        """Get current KYC status without circular import"""
        from kyc.models import KYCRequest
        try:
            latest_kyc = KYCRequest.objects.filter(
                user=self
            ).order_by('-created_at').first()
            return latest_kyc.status if latest_kyc else "not_submitted"
        except ObjectDoesNotExist:
            return "not_submitted"

    @property
    def is_kyc_completed(self):
        """Check if KYC is approved"""
        return self.kyc_status == "approved"

    @property
    def latest_kyc_request(self):
        """Get the latest KYC request details"""
        from kyc.models import KYCRequest
        return KYCRequest.objects.filter(
            user=self
        ).order_by('-created_at').first()

    def set_transaction_pin(self, raw_pin):
        """Securely set the transaction PIN"""
        self.transaction_pin = make_password(raw_pin)
        self.save()

    def verify_transaction_pin(self, raw_pin):
        """Verify the transaction PIN"""
        return check_password(raw_pin, self.transaction_pin)

    def __str__(self):
        return f"{self.username} - {self.kyc_status}"

class USDAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    account_id = models.CharField(max_length=6, unique=True, editable=False)
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                  validators=[MinValueValidator(Decimal('0.00'))])  # Store in USD
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def generate_unique_account_id():
        while True:
            # Generate a random 6-digit number
            account_id = str(random.randint(100000, 999999))
            # Check if it is unique
            if not USDAccount.objects.filter(account_id=account_id).exists():
                return account_id

    def save(self, *args, **kwargs):
        # Generate account_id only if it's not already set (i.e., on creation)
        if not self.account_id:
            self.account_id = self.generate_unique_account_id()
        super().save(*args, **kwargs)

    def update_balance(self, amount):
        """
        Update the balance of the account.
        Use a positive amount to increase the balance, negative to decrease.
        """
        if amount == 0:
            raise ValidationError("Amount must be non-zero.")

        with transaction.atomic():
            new_balance = self.balance + amount
            if new_balance < 0:
                raise ValidationError("Insufficient balance")

            self.balance = new_balance
            self.save()

    def deposit(self, amount):
        """Credit account with deposit."""
        if amount <= 0:
            raise ValidationError("Deposit amount must be positive.")
        self.update_balance(amount)

    def withdraw(self, amount):
        if self.balance >= amount:
            self.balance -= amount
            self.save()
        else:
            raise ValidationError("Insufficient funds")

    def get_transaction_history(self):
        """Retrieve all transactions for the user's account."""
        return Transaction.objects.filter(user=self.user).order_by('-created_at')

    def deduct_balance(self, amount):
        """
        Safely deduct amount from balance using F() expression to prevent race conditions
        """
        if self.balance < amount:
            raise ValueError("Insufficient balance")
            
        self.balance = F('balance') - amount
        self.save()
        # Refresh from db to get the actual new balance
        self.refresh_from_db()
        return self.balance

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(balance__gte=0),
                name='non_negative_balance'
            )
        ]

    def __str__(self):
        return f"{self.user} - Balance: ${self.balance}"

class ExchangeRate(models.Model):
    currency_code = models.CharField(max_length=3, unique=True)  # e.g., 'NGN'
    rate_to_usd = models.FloatField()  # e.g., 1350.0 (1 USD = 1350 NGN)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"1 USD = {self.rate_to_usd} {self.currency_code}"
        
class Fee(models.Model):
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    flat_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    percentage_fee = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.transaction_type.capitalize()} Fee"

    def calculate_fee(self, amount):
        # Ensure the amount is a Decimal
        amount = Decimal(amount)
        percentage_cost = (self.percentage_fee / Decimal(100)) * amount
        total_fee = self.flat_fee + percentage_cost
        return total_fee

    @classmethod
    def apply_transaction_fee(cls, transaction_type, amount):
        # Ensure the amount is a Decimal
        amount = Decimal(amount)
        fee = cls.objects.get(transaction_type=transaction_type, is_active=True)
        fee_amount = fee.calculate_fee(amount)
        total_amount = amount + fee_amount
        return total_amount, fee_amount

class Transaction(models.Model):
    STATUS_CHOICES = [
        ("initiated", "Initiated"),
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ]
    TRANSACTION_TYPES = [
        ('deposit', 'Deposit'),
        ('withdraw', 'Withdraw'),
        ('transfer', 'Transfer'),
        ("airtime", "Airtime Top-Up"),
        ("utility", "Utility Payment"),
        ('data', 'Data Bundle'),
        ("gift_card", "Gift Card Order"),
        ('shopping', 'Shopping'),
        ('subscription', 'Subscription'),
        ('commission', 'Commission')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_index=True)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    fee_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    initial_deposit_amount = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True, help_text="Original amount deposited before conversion")
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    description = models.TextField(null=True, blank=True)
    details = models.JSONField()
    payment_method = models.CharField(max_length=255)
    gateway = models.CharField(max_length=255)
    memo = models.CharField(max_length=255, unique=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    destination_account = models.CharField(max_length=255)
    error_message = models.TextField(null=True, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    external_reference = models.CharField(max_length=255, null=True, blank=True)
    geolocation = models.CharField(max_length=255, null=True, blank=True)
    currency = models.CharField(max_length=255)
    currency_from = models.CharField(max_length=255)
    target_currency = models.CharField(max_length=255)
    operator_id = models.CharField(max_length=255, null=True, blank=True)
    recipient_phone = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} - {self.transaction_type} - {self.status}"

class PlatformAccount(models.Model):
    name = models.CharField(max_length=20, unique=True)
    balance = models.DecimalField(max_digits=20, decimal_places=2, default=0,
                                  validators=[MinValueValidator(Decimal('0.00'))])
    address = models.CharField(max_length=50, unique=True, null=True, blank=True)
    account_type = models.CharField(
        max_length=50,
        choices=[("vault", "Vault"), ("utilities_pool", "Utilities Pool"), ("commission_pool", "Commission Pool")], null=True, blank=True)
    unique_id = models.CharField(max_length=6, default=generate_unique_id, editable=False, unique=True)

    def __str__(self):
        return self.name  # No parentheses

    def deposit(self, amount):
        """Deposit funds to the platform account"""
        if amount <= 0:
            raise ValidationError("Deposit amount must be positive")
        self.balance += amount
        self.save()

    def withdraw(self, amount):
        """Withdraw funds from the platform account"""
        if amount <= 0:
            raise ValidationError("Withdrawal amount must be positive")
        if amount > self.balance:
            raise ValidationError("Insufficient funds in platform account")
        self.balance -= amount
        self.save()

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(balance__gte=0),
                name='platform_non_negative_balance'
            )
        ]

class LinkedAccount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    bank_account_id = models.CharField(max_length=255, unique=True, blank=True, null=True)
    account_number = models.CharField(
        max_length=20,
        validators=[RegexValidator(regex=r'^\d+$', message="Account number must be numeric.")]
    )
    routing_number = models.CharField(
        max_length=9,
        validators=[RegexValidator(regex=r'^\d{9}$', message="Routing number must be exactly 9 digits.")]
    )
    bank_name = models.CharField(max_length=255)
    default = models.BooleanField(default=False)

    billing_name = models.CharField(max_length=255)
    billing_city = models.CharField(max_length=255)
    billing_country = models.CharField(max_length=2)
    billing_line1 = models.CharField(max_length=255)
    billing_district = models.CharField(max_length=255)
    billing_postal_code = models.CharField(max_length=20)

    bank_address_line1 = models.CharField(max_length=255)
    bank_address_city = models.CharField(max_length=255)
    bank_address_country = models.CharField(max_length=2)
    bank_address_district = models.CharField(max_length=255)

    class Meta:
        unique_together = ('user', 'account_number')

    def __str__(self):
        return f"{self.bank_name} linked to {self.user.username}"

class Alert(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)
    flags = models.JSONField()
    reviewed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Alert for {self.transaction} with flags {self.flags}"

class HighRiskCountry(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    message = models.TextField()
    type = models.CharField(max_length=50)  # Example: 'transaction', 'update', etc.
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)  # Track read timestamp
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def mark_as_read(self):
        from django.utils.timezone import now
        self.is_read = True
        self.read_at = now()  # Set the timestamp
        self.save()

# Rewards
class UserPoints(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    points = models.PositiveIntegerField(default=0)
    last_activity = models.DateTimeField(auto_now=True)

    daily_earned = models.PositiveIntegerField(default=0)  # Reset daily
    weekly_earned = models.PositiveIntegerField(default=0)  # Reset weekly
    last_reset = models.DateTimeField(default=now)  # Track last reset

    DAILY_LIMIT = 50
    WEEKLY_LIMIT = 450

    def reset_limits_if_needed(self):
        """ Reset daily and weekly limits based on time """
        today = now()
        if self.last_reset.date() != today.date():
            self.daily_earned = 0  # Reset daily points
            if today.weekday() == 0:  # Monday
                self.weekly_earned = 0  # Reset weekly points
            self.last_reset = today
            self.save()

    def can_earn_points(self, amount):
        """ Checks if user can earn points without exceeding limits """
        self.reset_limits_if_needed()
        return (
            self.daily_earned + amount <= self.DAILY_LIMIT and
            self.weekly_earned + amount <= self.WEEKLY_LIMIT
        )

    def add_points(self, amount, reason):
        """ Adds points if within limits """
        self.reset_limits_if_needed()
        if self.can_earn_points(amount):
            self.points += amount
            self.daily_earned += amount
            self.weekly_earned += amount
            self.last_activity = now()
            self.save()
            PointTransaction.objects.create(user=self.user, points=amount, transaction_type='earn', reason=reason)
            return True
        return False  # Exceeds limit

    def deduct_points(self, amount, description=""):
        """
        Deducts points if the user has enough; otherwise, returns False.
        """
        if self.points >= amount:
            self.points -= amount
            self.save()

            # Log the transaction
            PointTransaction.objects.create(
                user=self.user,
                points=-amount,  # Negative for deductions
                description=description
            )
            return True
        return False

class PointTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('earn', 'Earned'),
        ('redeem', 'Redeemed'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    points = models.IntegerField()  # Can be negative when redeeming
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    reason = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

class Reward(models.Model):
    name = models.CharField(max_length=100)
    points_required = models.PositiveIntegerField()
    description = models.TextField()
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name
    
class Referral(models.Model):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    
    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
    ]

    referrer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='referrals_made'
    )
    referred_user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='referred_by'
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=PENDING
    )
    created_at = models.DateTimeField(default=timezone.now)
    approved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.referrer} → {self.referred_user} ({self.status})"

    class Meta:
        unique_together = ('referrer', 'referred_user')
        
# Email
class EmailTemplate(models.Model):
    name = models.CharField(max_length=255, unique=True)
    subject = models.CharField(max_length=255)
    html_content = models.TextField()

    def preview(self):
        return format_html('<a href="/admin/email-preview/{}/" target="_blank">Preview</a>', self.id)

    def __str__(self):
        return self.name

class EmailLog(models.Model):
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=[('Sent', 'Sent'), ('Failed', 'Failed')])
    response = models.TextField()
    status_code = models.PositiveSmallIntegerField()
    template_used = models.CharField(max_length=255)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    request_id = models.CharField(max_length=100, blank=True, null=True)
    
    def __str__(self):
        return f"{self.subject} to {self.recipient} ({self.status_code})"

class PromotionalEmail(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    subject = models.CharField(max_length=255)
    body = models.TextField()
    recipients = models.ManyToManyField(User)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.subject



