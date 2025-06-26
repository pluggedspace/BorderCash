from django.contrib import admin, messages
from .models import Backup, BackupUpload, BackupJob
from django.core.management import call_command
import tempfile

from django.utils.safestring import mark_safe
from django.core.management import call_command
import os


@admin.register(Backup)
class BackupAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'created_at', 'drive_link', 'backup_size']
    actions = ['create_backup']

    def drive_link(self, obj):
        if obj.drive_url:
            return mark_safe(f'<a href="{obj.drive_url}" target="_blank">🔗 View on Drive</a>')
        return "-"
    drive_link.short_description = "Drive URL"

    def create_backup(self, request, queryset):
        # Always include media and DB when using the admin button
        call_command('create_backup', include_db=True, include_media=True)
        self.message_user(request, "✅ Backup initiated and should appear in the table.")
    create_backup.short_description = "Create system backup"


@admin.register(BackupUpload)
class BackupUploadAdmin(admin.ModelAdmin):
    list_display = ['file', 'uploaded_at']
    readonly_fields = ['uploaded_at']
    actions = None

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        zip_path = obj.file.path

        try:
            # Call restore command
            call_command('restore_backup', zip_path)
            self.message_user(request, f"✅ Restore complete from: {zip_path}", messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f"❌ Restore failed: {e}", messages.ERROR)


@admin.register(BackupJob)
class BackupJobAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'include_media', 'include_db']
    filter_horizontal = ()
    actions = ['run_backup_now']

    def run_backup_now(self, request, queryset):
        for job in queryset:
            apps = job.apps
            call_command('create_backup', apps=','.join(apps), include_media=job.include_media, include_db=job.include_db)
        self.message_user(request, "Backup job(s) started.", level=messages.INFO)
    run_backup_now.short_description = "Run selected backup jobs"
