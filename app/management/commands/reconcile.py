from django.core.management.base import BaseCommand
from app.services.reconciliation import run_reconciliation  # Adjust import path if necessary


class Command(BaseCommand):
    help = 'Run the reconciliation process'

    def handle(self, *args, **kwargs):
        self.stdout.write("Starting reconciliation process...")
        run_reconciliation()  # Call your reconciliation function
        self.stdout.write("Reconciliation process completed.")


# Example cronjob
"""0 0 * * * /path/to/your/virtualenv/bin/python /path/to/your/project/manage.py reconcile"""
