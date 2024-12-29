import logging
import os

from kyc.services.image_processing import ImageProcessing
from kyc.services.notification import Notification
from kyc.services.verification import Verification

logger = logging.getLogger(__name__)


# Helper for verifying ID documents and selfie
def verify_id(id_document_path, selfie_path):
    try:
        if not ImageProcessing.check_image_integrity(id_document_path) or not ImageProcessing.check_image_integrity(
                selfie_path):
            logger.warning("Image integrity check failed.")
            return False

        if not ImageProcessing.compare_images(id_document_path, selfie_path):
            logger.warning("Image comparison failed.")
            return False

        if not ImageProcessing.verify_faces(id_document_path, selfie_path):
            logger.warning("Face verification failed.")
            return False

        logger.info("ID verification successful.")
        return True
    except Exception as e:
        logger.error(f"ID verification error: {e}")
        return False


# Main KYC verification flow
def verify_user_kyc(user, id_document_path, selfie_path, address):
    api_key = os.getenv('LOCATIONIQ_API_KEY')  # API key from environment
    if verify_id(id_document_path, selfie_path):
        if Verification.verify_address(address, api_key):
            aml_check = Verification.run_aml_check(user)
            if all(status == True for status in aml_check.values()):
                Notification.send_approval_notification(user)
                return "KYC Approved"
            else:
                logger.warning("AML Check Failed.")
                return "AML Check Failed"
        else:
            logger.warning("Address Verification Failed.")
            return "Address Verification Failed"
    else:
        return 'ID Verification Failed'


# KYC process with logging and user profile reference
def process_kyc(kyc_request):
    logger.info(f'Starting KYC processing for user {kyc_request.user_profile.user}')
    try:
        verification_result = verify_kyc(kyc_request)
        kyc_request.status = verification_result
        kyc_request.save()

        if verification_result == 'approved':
            logger.info('KYC approved successfully.')
            Notification.send_approval_notification(kyc_request.user_profile.user)
        else:
            logger.warning(f'KYC rejected: {verification_result}')
    except Exception as e:
        logger.error(f'Error processing KYC for user {kyc_request.user_profile.user}: {e}')


# Central verification function using helper methods
def verify_kyc(kyc_request):
    if not verify_id(kyc_request.id_document, kyc_request.selfie):
        return 'rejected: ID verification failed'

    api_key = 'pk.10bfa8852fcb5b465d8247a86c3170a5'
    if not Verification.verify_address(kyc_request.address_document, api_key):
        return 'rejected: Address verification failed'

    aml_check_result = Verification.run_aml_check(kyc_request.user_profile.user)
    if not all(status == True for status in aml_check_result.values()):
        return 'rejected: AML check failed'

    return 'approved'
