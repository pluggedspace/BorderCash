import logging
from celery import shared_task
from kyc.models import KYCRequest
from app.models import UserProfile, Notification
from celery import shared_task
from django.core.mail import send_mail
from django.utils.timezone import now


logger = logging.getLogger(__name__)


@shared_task(bind=True)
def async_process_kyc(self, kyc_request_id):
    from kyc.services.services import process_kyc_task
    """
    Asynchronously process the KYC request by its ID.
    """
    try:
        kyc_request = KYCRequest.objects.get(id=kyc_request_id)
        logger.info(f'Starting KYC processing for request ID {kyc_request_id}.')

        # Call the process_kyc function to handle the actual processing
        process_kyc_task(kyc_request_id)
        logger.info(f'KYC processing completed for request ID {kyc_request_id}.')

    except KYCRequest.DoesNotExist:
        logger.error(f'KYC request with ID {kyc_request_id} does not exist.')
        self.retry(countdown=60, max_retries=3)  # Retry after 60 seconds, up to 3 times
    except Exception as e:
        logger.error(f'Error processing KYC request ID {kyc_request_id}: {str(e)}')
        self.retry(countdown=60, max_retries=3)  # Retry after 60 seconds for any exception

@shared_task
def process_kyc_task(kyc_request_id=None):
    """
    Processes the KYC request after 5 minutes and sends email notifications.
    """
    if kyc_request_id is None:
        logger.error("No KYC request ID provided. Task cannot proceed.")
        return

    try:
        kyc_request = KYCRequest.objects.get(id=kyc_request_id)
        user_profile = kyc_request.user

        # Simulating KYC processing logic
        verification_result = "approved"  # In real case, replace with actual verification logic

        # Update KYC request & profile
        kyc_request.status = verification_result
        kyc_request.verified_at = now()
        kyc_request.save()

        user_profile.kyc_status = verification_result
        user_profile.is_kyc_completed = verification_result == "approved"
        user_profile.save()

        # Send email notification
        subject = "KYC Verification Update"
        message = (
            f"Dear {user_profile.user.username},\n\n"
            f"Your KYC verification has been {verification_result.upper()}.\n"
            "You can check your status in the app."
        )

        send_mail(
            subject, message, "no-reply@mail.swifwallet.com",
            [user_profile.user.email], fail_silently=False
        )

        logger.info(f"KYC request {kyc_request_id} processed successfully.")

    except KYCRequest.DoesNotExist:
        logger.error(f"KYC request {kyc_request_id} not found.")
    except Exception as e:
        logger.error(f"Error processing KYC request {kyc_request_id}: {str(e)}", exc_info=True)

api_key = settings.LOCATIONIQ_API_KEY


@shared_task
def send_notification_task(user_id, message):
    user = UserProfile.objects.get(pk=user_id)
    Notification.objects.create(
        title='KYC Status',
        user=user,
        message=message,
        type='KYC Status'
    )
