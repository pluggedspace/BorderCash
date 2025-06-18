import logging
import os
import tempfile
from .dropbox import DropboxService
from kyc.services.notification import Notification
from kyc.services.verification import Verification
from .image_processing import ImageProcessing

logger = logging.getLogger(__name__)

def verify_id(dropbox_id_path, dropbox_selfie_path):
    """
    Verify an ID document and a selfie stored on Dropbox.
    Returns True if verification passes all checks.
    """
    temp_files = []
    try:
        # Get Dropbox service instance
        dropbox_service = DropboxService.get_instance()
        
        # Download images from Dropbox
        id_content = dropbox_service.download_file(dropbox_id_path)  # Expecting bytes
        selfie_content = dropbox_service.download_file(dropbox_selfie_path)  # Expecting bytes

        if not id_content or not selfie_content:
            logger.warning("Failed to download one or both images from Dropbox.")
            return False

        # Save images to temporary files
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as id_temp, \
             tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as selfie_temp:
            
            id_temp.write(id_content)
            selfie_temp.write(selfie_content)
            
            id_temp_path = id_temp.name
            selfie_temp_path = selfie_temp.name
            
            temp_files.extend([id_temp_path, selfie_temp_path])

        # Run verification checks
        verification_steps = [
            ("Image integrity", lambda: (
                ImageProcessing.check_image_integrity(id_temp_path) and 
                ImageProcessing.check_image_integrity(selfie_temp_path)
            )),
            ("Image comparison", lambda: ImageProcessing.compare_images(id_temp_path, selfie_temp_path)),
            ("Face verification", lambda: ImageProcessing.verify_faces(id_temp_path, selfie_temp_path))
        ]

        for step_name, check_func in verification_steps:
            if not check_func():
                logger.warning(f"ID verification failed at step: {step_name}")
                return False

        logger.info("ID verification successful")
        return True

    except Exception as e:
        logger.error(f"ID verification error: {str(e)}", exc_info=True)
        return False
        
    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                logger.warning(f"Failed to remove temporary file {temp_file}: {str(e)}")

def verify_user_kyc(user, dropbox_id_path, dropbox_selfie_path, dropbox_address_path):
    """
    Full KYC verification process: ID, selfie, and address.
    Returns 'approved' or 'rejected' based on verification results.
    """
    try:
        verification_steps = [
            ("ID verification", lambda: verify_id(dropbox_id_path, dropbox_selfie_path)),
            
            ("Address verification", 
             lambda: Verification.verify_address(
                 dropbox_address_path, 
                 os.getenv('LOCATIONIQ_API_KEY')
             )),
            
            ("AML check", 
             lambda: all(status for status in Verification.run_aml_check(user).values()))
        ]

        for step_name, check_func in verification_steps:
            if not check_func():
                logger.warning(f"KYC verification failed at step: {step_name}")
                return 'rejected'

        Notification.send_approval_notification(user)
        return 'approved'

    except Exception as e:
        logger.error(f"KYC verification error for user {user.id}: {str(e)}", exc_info=True)
        return 'rejected'

def process_kyc_task(kyc_request_id):
    """
    Processes the KYC request after 5 minutes and sends email notifications.
    """
    try:
        kyc_request = KYCRequest.objects.get(id=kyc_request_id)
        user_profile = kyc_request.user
        
        # Get verification result from the verification service
        verification_result = verify_user_kyc(
            user=user_profile,
            dropbox_id_path=kyc_request.id_document,
            dropbox_selfie_path=kyc_request.selfie,
            dropbox_address_path=kyc_request.address_document
        )
        
        # Update KYC request - this is what actually changes the kyc_status
        kyc_request.status = verification_result
        kyc_request.verified_at = now()
        kyc_request.save()
        
        # Send email notification
        subject = "KYC Verification Update"
        message = (
            f"Dear {user_profile.user.username},\n\n"
            f"Your KYC verification has been {verification_result.upper()}.\n"
            "You can check your status in the app."
        )
        send_mail(
            subject, message, "mail@border.cash",
            [user_profile.user.email], fail_silently=False
        )
        logger.info(f"KYC request {kyc_request_id} processed successfully.")
    except KYCRequest.DoesNotExist:
        logger.error(f"KYC request {kyc_request_id} not found.")
    except Exception as e:
        logger.error(f"Error processing KYC request {kyc_request_id}: {str(e)}", exc_info=True)