import requests
import os
import json
from django.template.loader import render_to_string
from django.template.exceptions import TemplateDoesNotExist
from django.utils.html import strip_tags
from django.conf import settings
from app.models import EmailLog

# Constants
ZEPTO_API_KEY = os.getenv('ZEPTO_API_KEY')
ZEPTO_API_URL = "https://api.zeptomail.com/v1.1/email"
EMAIL_TEMPLATES_BASE_PATH = 'emails/'  # Base path for all email templates

def get_template_path(template_name):
    """Construct and validate template path."""
    if not template_name.endswith('.html'):
        template_name = f"{template_name}.html"
    return os.path.join(EMAIL_TEMPLATES_BASE_PATH, template_name).replace('\\', '/')

def validate_template_exists(template_path):
    """Check if template exists in any template directory."""
    for template_dir in settings.TEMPLATES[0]['DIRS']:
        full_path = os.path.join(template_dir, template_path)
        if os.path.exists(full_path):
            return True
    return False

def send_email(subject, recipient, template_name, context):
    """Send email via ZeptoMail API with correct formatting"""
    if not ZEPTO_API_KEY:
        raise ValueError("ZEPTO_API_KEY not set!")

    try:
        # Get and check template
        template_path = get_template_path(template_name)
        if not validate_template_exists(template_path):
            raise TemplateDoesNotExist(f"Template '{template_path}' not found.")

        html_content = render_to_string(template_path, context)
        
        # Construct payload in exact ZeptoMail format
        payload = {
            "from": {
                "address": "Mail@border.cash"  # Case-sensitive
            },
            "to": [{
                "email_address": {
                    "address": recipient,
                    "name": context.get('username', 'User')
                }
            }],
            "subject": subject,
            "htmlbody": html_content
        }

        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
            'authorization': f'Zoho-enczapikey {ZEPTO_API_KEY}'
        }

        # Convert payload to JSON string to match your working example
        json_payload = json.dumps(payload, indent=4)
        print(f"Sending payload:\n{json_payload}")  # Debug output
        
        response = requests.post(
            ZEPTO_API_URL,
            data=json_payload,
            headers=headers,
            timeout=10
        )

        # Successful responses (200-299)
        if 200 <= response.status_code < 300:
            response_data = response.json()
            print(f"Email accepted by ZeptoMail. Request ID: {response_data.get('request_id')}")
            
            EmailLog.objects.create(
                recipient=recipient,
                subject=subject,
                status_code=response.status_code,
                template_used=template_name,
                request_id=response_data.get('request_id')
            )
            return True

        # Handle actual errors (400+)
        error_data = response.json()
        raise requests.HTTPError(
            f"ZeptoMail API Error ({response.status_code}): {error_data}"
        )

    except Exception as e:
        EmailLog.objects.create(
            recipient=recipient,
            subject=subject,
            status_code=500,
            template_used=template_name,
            error_message=str(e)
        )
        raise