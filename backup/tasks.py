from celery import shared_task
from django.core.management import call_command

@shared_task
def run_backup_task():
    try:
        call_command('create_backup', include_media=True, include_db=True)
        return "? Backup completed successfully"
    except Exception as e:
        return f"? Backup failed: {e}"
