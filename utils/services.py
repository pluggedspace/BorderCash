import logging
from decimal import Decimal
import requests
from django.conf import settings
from django.core.cache import cache
from django.db import transaction

from app.models import USDAccount, PlatformAccount, Transaction

logger = logging.getLogger(__name__)


class ReloadlyAuthService:
    AUDIENCE_URLS = {
        "topups": "https://topups-sandbox.reloadly.com",
        "giftcards": "https://giftcards-sandbox.reloadly.com",
        "utilities": "https://utilities-sandbox.reloadly.com",
    }

    @classmethod
    def get_audience_url(cls, service_type=None):
        """
        Dynamically select audience URL based on service type.
        Fallback to default URL if service type is not recognized.
        """
        return cls.AUDIENCE_URLS.get(service_type, settings.RELOADLY_BASE_URL)

    @classmethod
    def get_access_token(cls, service_type=None):
        """
        Get access token with dynamic service type handling
        """
        # Use a more flexible caching key
        cache_key = f"reloadly_token_{service_type}"

        token = cache.get(cache_key)
        if not token:
            # Dynamically determine the audience URL
            audience_url = cls.get_audience_url(service_type)

            url = f"{settings.RELOADLY_BASE_URL}/oauth/token"
            payload = {
                "client_id": settings.RELOADLY_CLIENT_ID,
                "client_secret": settings.RELOADLY_CLIENT_SECRET,
                "grant_type": "client_credentials",
                "audience": audience_url
            }
            try:
                response = requests.post(url, data=payload)
                response.raise_for_status()
                token_data = response.json()
                token = token_data.get("access_token")

                # Cache with a flexible timeout, default to 1 hour
                cache.set(cache_key, token, timeout=3600)
            except requests.RequestException as e:
                logger.error(f"Failed to get Reloadly token for service type {service_type}: {e}")
                raise RuntimeError(f"Failed to get Reloadly token for service type {service_type}: {e}")
        return token


class ReloadlyBaseService:
    @classmethod
    def make_request(cls, endpoint, method="GET", data=None, service_type=None):
        audience_url = ReloadlyAuthService.get_audience_url(service_type)
        url = f"{audience_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {ReloadlyAuthService.get_access_token(service_type)}",
            "Content-Type": "application/json",
        }
        try:
            response = requests.request(method, url, json=data, headers=headers)
            response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code
        except requests.RequestException as e:
            logger.error(
                f"Failed to make Reloadly API request for service type {service_type}: {e}. URL: {url}. Payload: {data}. Response: {response.text if response else 'No response'}")
            raise RuntimeError(f"Failed to make Reloadly API request for service type {service_type}: {e}")
        return response.json()


class AirtimeService:
    @staticmethod
    def top_up(user, phone_number, operator_id, amount):
        try:
            with transaction.atomic():
                user_account = USDAccount.objects.select_for_update().get(user=user)
                amount = Decimal(amount)

                if user_account.balance < amount:
                    raise ValueError("Insufficient balance")

                user_account.balance -= amount
                user_account.save()

                service_type = "topups"
                endpoint = f"/topups"
                payload = {
                    "recipientPhone": phone_number,
                    "operatorId": operator_id,
                    "amount": str(amount),
                }
                result = ReloadlyBaseService.make_request(endpoint, method="POST", data=payload,
                                                          service_type=service_type)

                reloadly_account = PlatformAccount.objects.get(name="ReloadlyAccount")
                paid_account = PlatformAccount.objects.get(name="PaidUtility")

                reloadly_account.balance -= amount
                reloadly_account.save()

                paid_account.balance += amount
                paid_account.save()

                Transaction.objects.create(
                    user=user,
                    platform_account=paid_account,
                    transaction_type="airtime",
                    amount=amount,
                    details=result,
                )

            return result

        except ValueError as e:
            logger.error(f"User {user.id} attempted airtime top-up but had insufficient balance: {e}")
            raise e

        except RuntimeError as e:
            logger.error(f"Failed to process airtime top-up for user {user.id}: {e}")
            raise e

        except Exception as e:
            logger.error(f"Unexpected error during airtime top-up for user {user.id}: {e}")
            raise RuntimeError("An error occurred during the airtime top-up process.")


class UtilityService:
    @staticmethod
    def fetch_billers():
        endpoint = "/utilities/billers"
        result = ReloadlyBaseService.make_request(endpoint, method="GET", service_type="utilities")

        if result.get('success'):
            return result.get('billers', [])
        else:
            raise RuntimeError("Failed to fetch billers")

    @staticmethod
    def pay_bill(user, account_number, provider_id, amount, commission=0.00):
        with transaction.atomic():
            user_account = USDAccount.objects.select_for_update().get(user=user)

            total_deduction = amount + commission

            if user_account.balance < total_deduction:
                raise ValueError("Insufficient balance for the transaction")

            user_account.balance -= total_deduction
            user_account.save()

            service_type = "utilities"
            endpoint = f"/utilities"
            payload = {
                "accountNumber": account_number,
                "providerId": provider_id,
                "amount": amount,
            }

            try:
                result = ReloadlyBaseService.make_request(endpoint=endpoint, method="POST", data=payload,
                                                          service_type=service_type)
            except Exception as e:
                user_account.balance += total_deduction
                user_account.save()
                raise RuntimeError(f"Failed to process utility payment: {e}")

            reloadly_account = PlatformAccount.objects.get(name="ReloadlyAccount")
            paid_account = PlatformAccount.objects.get(name="PaidUtility")
            commissions_account = PlatformAccount.objects.get(name="Commissions")

            reloadly_account.balance -= amount
            reloadly_account.save()

            paid_account.balance += amount
            paid_account.save()

            if commission > 0:
                commissions_account.balance += commission
                commissions_account.save()

            Transaction.objects.create(
                user=user,
                platform_account=paid_account,
                transaction_type="utility",
                amount=amount,
                details=result,
            )

            if commission > 0:
                Transaction.objects.create(
                    user=None,
                    platform_account=commissions_account,
                    transaction_type="commission",
                    amount=commission,
                )

        return result


class GiftCardService:
    @staticmethod
    def purchase_gift_card(user, gift_card_id, amount, commission=0.00):
        with transaction.atomic():
            user_account = USDAccount.objects.select_for_update().get(user=user)
            total_deduction = amount + commission
            if user_account.balance < total_deduction:
                raise ValueError("Insufficient balance")

            user_account.balance -= total_deduction
            user_account.save()

            service_type = "giftcards"
            endpoint = f"/giftcards"
            payload = {
                "giftCardId": gift_card_id,
                "amount": amount,
            }
            result = ReloadlyBaseService.make_request(endpoint, method="POST", data=payload,
                                                      service_type=service_type)

            reloadly_account = PlatformAccount.objects.get(name="ReloadlyAccount")
            paid_account = PlatformAccount.objects.get(name="PaidUtility")
            commissions_account = PlatformAccount.objects.get(name="Commissions")

            reloadly_account.balance -= amount
            reloadly_account.save()

            paid_account.balance += amount
            paid_account.save()

            if commission > 0:
                commissions_account.balance += commission
                commissions_account.save()

            Transaction.objects.create(
                user=user,
                platform_account=paid_account,
                transaction_type="giftcard",
                amount=amount,
                details=result,
            )

            if commission > 0:
                Transaction.objects.create(
                    user=None,
                    platform_account=commissions_account,
                    transaction_type="commission",
                    amount=commission,
                )

        return result
