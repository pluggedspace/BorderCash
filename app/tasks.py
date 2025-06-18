from celery import shared_task
from django.utils.timezone import now, timedelta
from .models import UserPoints, PromotionalEmail, ExchangeRate
from django.core.mail import send_mail

import requests
from django.db import transaction
import logging
from celery.exceptions import Retry
from requests.exceptions import RequestException
from django.core.cache import cache


logger = logging.getLogger(__name__)


@shared_task
def expire_inactive_points():
    """ Deducts all points from inactive users after 3 months of no activity """
    three_months_ago = now() - timedelta(days=90)
    inactive_users = UserPoints.objects.filter(last_activity__lt=three_months_ago, points__gt=0)

    for user_points in inactive_users:
        user_points.points = 0  # Reset points
        user_points.save()
        print(f"Expired points for user {user_points.user}")


@shared_task
def send_promotional_email(email_id):
    email = PromotionalEmail.objects.get(id=email_id)
    recipients = email.recipients.all().values_list('email', flat=True)
    
    try:
        send_mail(
            subject=email.subject,
            message=email.body,
            from_email="mail@border.cash",
            recipient_list=list(recipients),
            fail_silently=False,
        )
        email.status = "sent"
        email.sent_at = now()
    except Exception as e:
        email.status = "failed"
    
    email.save()


@shared_task(bind=True, max_retries=3, default_retry_delay=300)  # 3 retries, 5 minutes apart
def update_exchange_rates(self):
    """
    Fetches current exchange rates from API and updates database.
    Implements retry logic, proper logging, and cache invalidation.
    """
    url = "https://open.er-api.com/v6/latest/USD"
    
    try:
        # Add timeout to prevent hanging (5 seconds connect, 10 seconds read)
        response = requests.get(url, timeout=(5, 10))
        response.raise_for_status()  # Raises HTTPError for bad responses
        
        data = response.json()

        # Validate API response structure
        if data.get("result") != "success":
            error_msg = f"API returned unsuccessful result: {data.get('result')}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        rates = data.get("rates", {})
        if not rates:
            error_msg = "No rates found in API response"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # Use atomic transaction for database updates
        with transaction.atomic():
            updated_codes = []
            for code, rate in rates.items():
                # Validate rate is a positive number
                if not isinstance(rate, (int, float)) or rate <= 0:
                    logger.warning(f"Invalid rate for {code}: {rate}. Skipping.")
                    continue
                    
                _, created = ExchangeRate.objects.update_or_create(
                    currency_code=code,
                    defaults={"rate_to_usd": rate}
                )
                updated_codes.append(code)
                
                # Clear cache for this currency
                cache.delete(f'exchange_rate_{code}')

            logger.info(f"Successfully updated {len(updated_codes)} exchange rates")
            return {"status": "success", "updated": updated_codes}

    except RequestException as e:
        error_msg = f"API request failed: {str(e)}"
        logger.error(error_msg)
        raise self.retry(exc=e)
        
    except ValueError as e:
        error_msg = f"Data validation error: {str(e)}"
        logger.error(error_msg)
        raise self.retry(exc=e)
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise self.retry(exc=e)