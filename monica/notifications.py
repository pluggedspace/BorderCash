from django.core.mail import send_mail

def send_notification(user, message):
    """ Sends a notification via email """
    send_mail(
        'Dispute Update',
        message,
        'support@swifwallet.com',
        [user.email],
        fail_silently=False,
    )



def notify_human_support(dispute):
    """Notify Swif's human support team about an escalated dispute."""
    subject = f"🚨 Escalated Dispute: {dispute.category} (User: {dispute.user.email})"
    message = f"""
    A dispute has been escalated for manual review.

    🔹 **User:** {dispute.user.email}
    🔹 **Category:** {dispute.category}
    🔹 **Transaction ID:** {dispute.transaction_id if dispute.transaction_id else "N/A"}
    🔹 **Description:** {dispute.description}
    🔹 **Created At:** {dispute.created_at.strftime('%Y-%m-%d %H:%M')}
    
    Please review and take appropriate action.
    """
    send_mail(subject, message, "support@swifwallet.com", ["support@swifwallet.com"])
