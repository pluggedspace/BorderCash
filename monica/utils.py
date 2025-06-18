import os
import requests
import logging
from groq import Groq
from django.core.exceptions import ObjectDoesNotExist
from django.utils.timezone import now
from django.core.cache import cache
from .models import FAQ
from app.models import USDAccount, Transaction
from difflib import get_close_matches
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)




# FAQ Sys
def find_faq_answer(user_query):
    faqs = FAQ.objects.all()
    questions = [faq.question for faq in faqs]
    best_match = get_close_matches(user_query, questions, n=1, cutoff=0.6)

    if best_match:
        faq = FAQ.objects.get(question=best_match[0])
        return faq.answer

    return None

def get_cached_faq_response(user_query):
    cache_key = f"faq_response:{user_query}"
    response = cache.get(cache_key)
    if response:
        return response
    
    response = find_faq_answer(user_query)
    if response:
        cache.set(cache_key, response, timeout=86400)  # Cache for 24 hours
    
    return response

# Initialize the Mixtral client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

def query_mixtral_stream(user, user_query):
    """
    Queries Mixtral with streaming enabled.
    """
    try:
        completion = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[{"role": "user", "content": user_query}],
            temperature=1,
            max_tokens=1024,
            top_p=1,
            stream=True,  # Enable streaming
            stop=None,
        )

        for chunk in completion:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content  # Send tokens as they arrive

    except Exception as e:
        logger.error(f"Mixtral Streaming API Error: {e}")
        yield "⚠️ AI service is temporarily unavailable. Please try again later."

# Proactive Alerts

LOW_BALANCE_THRESHOLD = 10  # Move this to settings if you want configurability

def check_low_balance(user):
    try:
        account = USDAccount.objects.get(user=user)
        if account.balance < LOW_BALANCE_THRESHOLD:
            return f"⚠️ Your balance is low: ${account.balance:.2f}. Consider adding funds."
    except ObjectDoesNotExist:
        return "⚠️ No account found. Please set up your USD account."
    return None

def check_pending_transactions(user):
    pending_count = Transaction.objects.filter(user=user, status="pending").count()
    if pending_count > 0:
        return f"🔔 You have {pending_count} pending transaction(s). Please review them."
    return None

def send_alert(user, message):
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"user_{user.id}",
            {"type": "chat.message", "message": message},
        )
    except Exception as e:
        logger.error(f"Failed to send alert to user {user.id}: {e}")
