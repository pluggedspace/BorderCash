import zipfile
import os
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = "Restore system from backup zip"

    def add_arguments(self, parser):
        parser.add_argument('backup_file', type=str)

    def handle(self, *args, **options):
        backup_file = options['backup_file']

        if not os.path.exists(backup_file):
            raise FileNotFoundError("Backup file not found.")

        with zipfile.ZipFile(backup_file, 'r') as zip_ref:
            zip_ref.extractall(settings.BASE_DIR)
            zip_items = set(zip_ref.namelist())

        # Verification step: check that all files from the zip now exist in the filesystem
        missing_after_restore = set()
        for item in zip_items:
            extracted_path = os.path.join(settings.BASE_DIR, item)
            if not os.path.exists(extracted_path):
                missing_after_restore.add(item)
        if not missing_after_restore:
            self.stdout.write("✅ All files from the backup zip are present after restore.")
        else:
            self.stdout.write(f"❌ Missing files after restore: {missing_after_restore}")
        self.stdout.write("✅ Backup restored.")
