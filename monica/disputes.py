from .models import Dispute
from .tasks import process_refund
import requests
import logging
import os
from app.models import Transaction
from django.db import transaction as db_transaction
from groq import Groq
from django.utils import timezone
from datetime import timedelta


logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_ENDPOINT = "https://api.groq.com/v1/chat/completions"

def fetch_transaction_details(transaction_id):
    """Fetch transaction details from the database."""
    try:
        transaction = Transaction.objects.get(id=transaction_id)
        return {
            "status": transaction.status,  # 'completed', 'pending', 'failed'
            "amount": transaction.amount,
            "method": transaction.payment_method,  # 'card', 'crypto', 'bank'
            "timestamp": transaction.timestamp
        }
    except Transaction.DoesNotExist:
        return None

client = Groq(api_key=GROQ_API_KEY)

def call_mixtral_api(system_prompt, user_prompt, max_tokens=50):
    """Reusable function for calling Mixtral API using Groq SDK."""
    try:
        completion = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_completion_tokens=max_tokens,
            top_p=1,
        )

        return completion.choices[0].message.content.strip() if completion.choices else None

    except Exception as e:
        logger.error(f"Mixtral API request failed: {e}")
        return None

def classify_dispute(user_input):
    """Classifies the dispute based on keywords."""
    categories = {
        "failed transaction": "Failed Transaction",
        "duplicate charge": "Duplicate Charge",
        "unauthorized payment": "Unauthorized Payment",
        "service not received": "Service Not Received",
        "pending": "Transaction Still Pending"
    }
    
    # Convert input to lowercase and match category
    for keyword, category in categories.items():
        if keyword in user_input.lower():
            return category  # ✅ Only return the category name

    return "Other"

def get_ai_dispute_advice(user_input, category, transaction_id=None):
    """Get AI-generated dispute resolution advice with transaction details if available."""
    
    # Fetch transaction details if transaction_id is provided
    transaction_info = fetch_transaction_details(transaction_id) if transaction_id else None

    # Construct transaction details string properly
    transaction_details = "No transaction details available."
    if transaction_info:
        transaction_details = (
            f"- Status: {transaction_info['status']}\n"
            f"- Amount: {transaction_info['amount']}\n"
            f"- Payment Method: {transaction_info['method']}\n"
            f"- Timestamp: {transaction_info['timestamp']}"
        )

    # Construct message for AI
    message_content = (
        f"The user submitted a dispute: '{user_input}'.\n"
        f"Categorized as: {category}.\n\n"
        f"Transaction Details:\n{transaction_details}\n\n"
        "Based on this information, provide a concise response with a suggested next step.\n"
        "- If the transaction is pending, advise patience.\n"
        "- If failed, suggest contacting support or retrying.\n"
        "- If completed and the dispute is valid, guide the user on refund or resolution.\n"
        "Keep it short and professional."
    )

    system_prompt = "You are Swif's AI assistant for dispute resolution."
    return call_mixtral_api(system_prompt, message_content, max_tokens=100) or "Swif support will review your case shortly."



def handle_dispute(user, user_input, transaction_id=None):
    """Main function to handle user disputes, classify them, and determine the resolution path."""
    category = classify_dispute(user_input)
    transaction_info = fetch_transaction_details(transaction_id) if transaction_id else None

    # Create dispute entry atomically
    with db_transaction.atomic():
        dispute = Dispute.objects.create(
            user=user,
            transaction_id=transaction_id,
            category=category[:255],
            description=user_input[:255],
            status="pending",
            refund_status="not_applicable"
        )

        # Auto-refund logic
        if category in ["Failed Transaction", "Duplicate Charge"]:
            process_refund.delay(dispute.id)  # Use Celery task
            return f"Your dispute has been categorized as '{category}'. The refund is being processed."

    # Transaction-based advice
    if transaction_info:
        if transaction_info["status"] == "pending":
            return f"Your dispute has been categorized as '{category}'. Your transaction is still pending. Please allow time for processing."
        elif transaction_info["status"] == "failed":
            return f"Your dispute has been categorized as '{category}'. Your transaction failed. You may be eligible for a refund. Swif support will review your case."
        elif transaction_info["status"] == "completed":
            return f"Your dispute has been categorized as '{category}'. Your transaction was completed successfully. If you believe this is incorrect, Swif will investigate further."

    # Auto-escalation check
    if should_escalate(user, category, transaction_info):
        dispute.status = "escalated"
        dispute.save()
        notify_human_support(dispute)
        return f"Your dispute has been categorized as '{category}'. This case has been escalated to Swif's human support team."

    # AI-generated advice
    ai_advice = get_ai_dispute_advice(user_input, category, transaction_info)
    return f"Your dispute has been categorized as '{category}'. {ai_advice}"

def check_dispute_status(user):
    """Fetch and return formatted dispute status for a user."""
    disputes = Dispute.objects.filter(user=user).order_by('-created_at')

    if not disputes.exists():
        return "You have no active disputes."

    response = "📌 **Your Dispute Statuses:**\n"
    for dispute in disputes:
        response += (
            f"🔹 **{dispute.category}** - {dispute.status.upper()} "
            f"(Created: {dispute.created_at.strftime('%Y-%m-%d %H:%M')})\n"
        )
    
    return response


def should_escalate(user, category, transaction_info=None):
    """Determine if a dispute should be escalated to human support."""
    
    HIGH_AMOUNT_THRESHOLD = 1000  # Example threshold for high-value transactions
    ESCALATION_CATEGORIES = ["Fraudulent Transaction", "Unauthorized Charge", "Account Compromised"]
    
    # Escalate if the category matches a high-risk type
    if category in ESCALATION_CATEGORIES:
        return True

    # Escalate if the transaction amount is high
    if transaction_info and transaction_info["amount"] >= HIGH_AMOUNT_THRESHOLD:
        return True

    # Escalate if the user has multiple disputes in a short period
    recent_disputes = Dispute.objects.filter(user=user, created_at__gte=timezone.now() - timedelta(days=30))
    if recent_disputes.count() > 3:  # More than 3 disputes in the last 30 days
        return True

    return False

def notify_human_support(dispute):
    """Notify Swif’s human support team about an escalated dispute."""
    try:
        support_email = "support@swif.com"
        subject = f"🚨 Escalated Dispute: {dispute.category} (User: {dispute.user.username})"
        message = (
            f"A dispute has been escalated for manual review.\n\n"
            f"User: {dispute.user.username}\n"
            f"Transaction ID: {dispute.transaction_id if dispute.transaction_id else 'N/A'}\n"
            f"Category: {dispute.category}\n"
            f"Description: {dispute.description}\n"
            f"Status: {dispute.status}\n"
            f"Created At: {dispute.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            f"Please review and take necessary action."
        )
        
        # Send email notification (assuming Django's send_mail is configured)
        send_mail(subject, message, "no-reply@swifwallet.com", [support_email])

        # Log the notification
        logger.info(f"Human support notified for dispute ID {dispute.id}.")

    except Exception as e:
        logger.error(f"Error notifying human support: {e}")
