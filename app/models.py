import logging
import random
import uuid
from datetime import datetime
from decimal import Decimal
import requests
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import RegexValidator, MinValueValidator
from django.db import models, transaction
from rest_framework.exceptions import ValidationError

logger = logging.getLogger(__name__)
TRANSACTION_TYPES = (
    ('deposit', 'Deposit'),
    ('withdrawal', 'Withdrawal'),
    ('transfer', 'Transfer'),
    ('top-up', 'Top-up'),
)


def generate_unique_id():
    return str(uuid.uuid4())[:6]


class Region(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name  # No parentheses


class User(AbstractUser):
    email = models.EmailField(unique=True)

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_user_set',  # Change this to avoid clashes
        blank=True,
        help_text='The groups this user belongs to.',
        verbose_name='groups',
    )

    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_user_permissions_set',  # Change this to avoid clashes
        blank=True,
        help_text='Specific permissions for this user.',
        verbose_name='user permissions',
    )

    # Add any additional fields you need
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

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(balance__gte=0),
                name='non_negative_balance'
            )
        ]

    def __str__(self):
        return f"{self.user} - Balance: ${self.balance}"


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

    def link_account_to_circle(self):
        """
        Link this bank account to Circle's system and store the Circle `bank_account_id`.
        """
        url = "https://api-sandbox.circle.com/v1/businessAccount/banks/wires"
        headers = {
            "Authorization": f"Bearer {settings.CIRCLE_API}",
            "Content-Type": "application/json"
        }

        # Generate a unique idempotency key
        idempotency_key = str(uuid.uuid4())
        payload = {
            "idempotencyKey": idempotency_key,
            "billingDetails": {
                "name": self.billing_name,
                "city": self.billing_city,
                "country": self.billing_country,
                "line1": self.billing_line1,
                "district": self.billing_district,
                "postalCode": self.billing_postal_code,
            },
            "bankAddress": {
                "line1": self.bank_address_line1,
                "city": self.bank_address_city,
                "country": self.bank_address_country,
                "district": self.bank_address_district,
            },
            "accountNumber": self.account_number,
            "routingNumber": self.routing_number,
            "bankName": self.bank_name,
        }

        try:
            # Send the POST request to Circle's API
            response = requests.post(url, headers=headers, json=payload)
            response_data = response.json()

            # Log the status code and response data for debugging
            print(f"Response Status Code: {response.status_code}")
            print(f"Response Data: {response_data}")

            # Check if the response indicates success (201 Created or 200 OK)
            if response.status_code in (201, 200):  # Handle both successful and pending responses
                # Retrieve the Circle ID from the response
                circle_id = response_data.get('data', {}).get('id')
                if circle_id:
                    # Link the Circle ID to the model field
                    self.bank_account_id = circle_id  # Assign the Circle ID to bank_account_id
                    self.save()  # Save the updated model instance
                    return circle_id  # Return the saved Circle ID

                raise Exception("Circle ID not found in response data.")

            # Handle unexpected responses
            error_message = response_data.get("message", "An error occurred while linking the account")
            raise Exception(f"Circle API Error: {error_message}")

        except requests.RequestException as e:
            raise Exception(f"Request Error: {e}")

    def fetch_and_cross_match_circle_id(self):
        """
        Fetch bank accounts from Circle API and cross-match with local records to find the ID.
        """
        url = "https://api-sandbox.circle.com/v1/businessAccount/banks/wires"
        headers = {
            "Authorization": f"Bearer {settings.CIRCLE_API}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.get(url, headers=headers)
            response_data = response.json()

            if response.status_code == 200:  # Successfully retrieved
                matched_circle_id = None  # Initialize variable to store matched Circle ID

                for account in response_data.get('data', []):
                    # Log the account details for debugging
                    print("Checking Circle account:", account)

                    # Check if any existing LinkedAccount matches the Circle account
                    if (account['billingDetails']['name'] == self.billing_name and
                            account['bankAddress']['bankName'] == self.bank_name and
                            account['billingDetails']['line1'] == self.billing_line1 and
                            account['billingDetails']['city'] == self.billing_city and
                            account['billingDetails']['postalCode'] == self.billing_postal_code and
                            account['billingDetails']['district'] == self.billing_district and
                            account['billingDetails']['country'] == self.billing_country):
                        matched_circle_id = account['id']  # Store the matching ID
                        break  # Exit the loop once a match is found

                if matched_circle_id:
                    return matched_circle_id  # Return the matched Circle ID
                else:
                    print("No matching Circle account found.")  # Log if no match is found
                    return None

            else:
                error_message = response_data.get("message", "Failed to retrieve accounts")
                raise Exception(f"Circle API Error: {error_message}")

        except requests.RequestException as e:
            raise Exception(f"Request Error: {e}")


class Alert(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)
    flags = models.JSONField()
    reviewed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Alert for {self.transaction} with flags {self.flags}"


class ReconciliationHistory(models.Model):
    pass


class HighRiskCountry(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name
