from django.core.management.base import BaseCommand
from app.tasks import update_exchange_rates

class Command(BaseCommand):
    help = "Fetches latest exchange rates and saves to database"

    def handle(self, *args, **options):
        self.stdout.write("Updating exchange rates...")
        result = update_exchange_rates()  # Runs synchronously
        self.stdout.write(
            self.style.SUCCESS(f"Success! Updated {len(result['updated'])} currencies.")
        )
