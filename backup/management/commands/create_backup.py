import os
import shutil
import datetime
import zipfile
from django.core.management.base import BaseCommand
from django.conf import settings
from backup.drive_utils import upload_to_drive
import subprocess
import tempfile

default_apps = ['app', 'kyc', 'iban', 'invest', 'monica', 'drac']

class Command(BaseCommand):
    help = "Backup specific apps, DB and media, and upload to Google Drive"

    def handle(self, *args, **options):
        date = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_root = os.path.join(settings.BASE_DIR, "backups")
        os.makedirs(backup_root, exist_ok=True)

        backup_name = f"full_backup_{date}.zip"
        backup_path = os.path.join(backup_root, backup_name)

        # Apps to backup
        apps_to_backup = options.get('apps').split(',') if options.get('apps') else default_apps
        include_media = options.get('include_media', False)
        include_db = options.get('include_db', False)

        # Create zip file
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add each app's folder
            for app in apps_to_backup:
                app_path = os.path.join(settings.BASE_DIR, app)
                if os.path.isdir(app_path):
                    for root, dirs, files in os.walk(app_path):
                        for file in files:
                            full_path = os.path.join(root, file)
                            arcname = os.path.relpath(full_path, settings.BASE_DIR)
                            zipf.write(full_path, arcname)
                else:
                    self.stdout.write(f"WARNING: App folder not found: {app}")

            # Include media
            if include_media:
                media_root = getattr(settings, "MEDIA_ROOT", os.path.join(settings.BASE_DIR, "media"))
                if os.path.isdir(media_root):
                    for root, dirs, files in os.walk(media_root):
                        for file in files:
                            full_path = os.path.join(root, file)
                            arcname = os.path.relpath(full_path, settings.BASE_DIR)
                            zipf.write(full_path, arcname)

            # Include DB file
            if include_db:
                db_dump_path = os.path.join(tempfile.gettempdir(), f"db_backup_{date}.dump")
                dump_postgres_db(db_dump_path)
                zipf.write(db_dump_path, f"db_backup_{date}.dump")

        self.stdout.write(f"✅ Backup created: {backup_path}")

        # Verification step: check contents of the zip
        expected_items = set()
        for app in apps_to_backup:
            app_path = os.path.join(settings.BASE_DIR, app)
            if os.path.isdir(app_path):
                for root, dirs, files in os.walk(app_path):
                    for file in files:
                        arcname = os.path.relpath(os.path.join(root, file), settings.BASE_DIR)
                        expected_items.add(arcname)
        if include_media:
            media_root = getattr(settings, "MEDIA_ROOT", os.path.join(settings.BASE_DIR, "media"))
            if os.path.isdir(media_root):
                for root, dirs, files in os.walk(media_root):
                    for file in files:
                        arcname = os.path.relpath(os.path.join(root, file), settings.BASE_DIR)
                        expected_items.add(arcname)
        if include_db:
            expected_items.add(f"db_backup_{date}.dump")

        with zipfile.ZipFile(backup_path, 'r') as zipf:
            zip_items = set(zipf.namelist())
        missing = expected_items - zip_items
        extra = zip_items - expected_items
        if not missing:
            self.stdout.write("✅ All expected files are present in the backup zip.")
        else:
            self.stdout.write(f"❌ Missing files in backup: {missing}")
        if extra:
            self.stdout.write(f"⚠️ Extra files in backup: {extra}")

        # Upload to Google Drive
        try:
            uploaded_file = upload_to_drive(backup_path)
            self.stdout.write(f"☁️ Uploaded to Drive: {uploaded_file.get('webViewLink')}")
        except Exception as e:
            self.stdout.write(f"❌ Drive upload failed: {e}")

        # Cleanup old backups
        cleanup_old_backups(backup_root, max_backups=5)

    def add_arguments(self, parser):
        parser.add_argument('--apps', type=str, help='Comma-separated app names')
        parser.add_argument('--include_media', action='store_true')
        parser.add_argument('--include_db', action='store_true')

def cleanup_old_backups(folder, max_backups=5):
    files = sorted([os.path.join(folder, f) for f in os.listdir(folder)], key=os.path.getctime)
    if len(files) > max_backups:
        for f in files[:-max_backups]:
            os.remove(f)

def dump_postgres_db(output_path):
    db_url = settings.DATABASES['default']['NAME']
    user = settings.DATABASES['default'].get('USER', 'postgres')
    password = settings.DATABASES['default'].get('PASSWORD', '')
    host = settings.DATABASES['default'].get('HOST', 'localhost')
    port = settings.DATABASES['default'].get('PORT', '5432')

    os.environ['PGPASSWORD'] = password
    cmd = [
        'pg_dump',
        '-U', user,
        '-h', host,
        '-p', str(port),
        '-F', 'c',
        '-f', output_path,
        db_url
    ]
    subprocess.run(cmd, check=True)
    del os.environ['PGPASSWORD']
