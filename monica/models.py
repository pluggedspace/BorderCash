from django.db import models
from django.conf import settings
from app.models import Transaction, USDAccount
import uuid
from django.utils.timezone import now
from django.utils.text import slugify

from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
import uuid

User = get_user_model()


"""class AutomationSettings(models.Model):
    enable_automation = models.BooleanField(default=True)
    blog_frequency = models.IntegerField(default=2)  # Posts per week
    social_media_frequency = models.IntegerField(default=5)  # Posts per week

    def __str__(self):
        return "Automation Settings"

class AIContentPrompt(models.Model):
    PROMPT_TYPES = (
        ('blog', 'Blog Post'),
        ('social_media', 'Social Media Post'),
        ('email', 'Email Campaign'),
    )
    
    prompt = models.TextField(help_text="Enter the prompt to use for AI content generation")
    prompt_type = models.CharField(max_length=20, choices=PROMPT_TYPES, default='blog',
                                   help_text="The type of content this prompt will generate")
    last_updated = models.DateTimeField(auto_now=True, help_text="When this prompt was last modified")
    
    
    class Meta:
        verbose_name = "AI Content Prompt"
        verbose_name_plural = "AI Content Prompts"
        unique_together = ['prompt_type']  # Ensure only one prompt per type
    
    def __str__(self):
        return f"{self.get_prompt_type_display()} Prompt"
 
class BlogPost(models.Model):
    title = models.CharField(max_length=255)
    image_url = models.URLField(blank=True, null=True)
    content = models.TextField()
    slug = models.SlugField(unique=True, max_length=255) 
    keywords = models.TextField(blank=True, null=True)
    ai_generated = models.BooleanField(default=True)
    scheduled_time = models.DateTimeField(blank=True, null=True)
    approved = models.BooleanField(default=False)
    published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.ai_generated and not self.content:
            prompt = AIContentPrompt.get_prompt()
            self.content = generate_ai_content(prompt.format(title=self.title))
        
        if not self.image_url:
            self.image_url = fetch_image_from_pexels(self.title)

            
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title"""

class FAQ(models.Model):
    question = models.CharField(max_length=255, unique=True)
    answer = models.TextField()
    published = models.BooleanField(default=False)
    approved = models.BooleanField(default=False)

    def __str__(self):
        return self.question


class Dispute(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('escalated', 'Escalated'),
        ('closed', 'Closed'),
    ]
    
    REFUND_STATUS_CHOICES = [
        ('not_applicable', 'Not Applicable'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    transaction_id = models.UUIDField(null=True, blank=True)
    category = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    refund_status = models.CharField(max_length=20, choices=REFUND_STATUS_CHOICES, default='not_applicable')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def process_refund(self):
        """ Triggers a refund asynchronously via Celery """
        from .tasks import process_refund  # Import Celery task

        if self.refund_status in ["completed", "failed"]:
            return False  # Refund already processed, avoid duplication
        
        if self.transaction_id:
            self.refund_status = 'processing'
            self.status = 'in_progress'
            self.save()
            process_refund.delay(self.id)  # Run refund in background
            return True
        return False

    def __str__(self):
        return f"{self.user} - {self.category} ({self.status})"

class RefundLog(models.Model):
    """Stores records of all refunds processed"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="refunds")
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE)
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.TextField()
    refund_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Refund {self.transaction.transaction_id} - {self.refund_amount}"
