import logging


class Notification:

    @staticmethod
    def send_approval_notification(user):
        try:
            user.email_user('KYC Approved', 'Your KYC has been successfully verified.')
            return True
        except Exception as e:
            logging.error(f"Failed to send email: {e}")
            return False
