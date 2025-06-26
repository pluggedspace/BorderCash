# myapp/cron.py
from django.core.management import call_command

def scheduled_backup():
    call_command('create_backup')
