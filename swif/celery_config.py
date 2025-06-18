from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# Set default Django settings module for 'celery'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'swif.settings')

app = Celery('swif')

# Load task modules from all registered Django app configs.
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'expire-points-daily': {
        'task': 'points.tasks.expire_inactive_points',
        'schedule': crontab(hour=0, minute=0),  # Runs daily at midnight
    },
    "check_accounts_every_60min": {
        "task": "monica.tasks.monitor_user_accounts",
        "schedule": crontab(minute="*/60"),  # Runs every 60 minutes
    },
    'notify_support_daily': {
        'task': 'dispute.tasks.notify_support_about_escalated_disputes',
        'schedule': crontab(hour=0, minute=0),  # Runs daily at midnight
    },
}

