from django.core.exceptions import ValidationError
from django.db import models

APP_CHOICES = [
    ('app', 'App'),
    ('kyc', 'KYC'),
    ('iban', 'IBAN'),
    ('invest', 'Invest'),
    ('monica', 'Monica'),
    ('drac', 'Drac'),
]

def validate_zip(value):
    if not value.name.endswith('.zip'):
        raise ValidationError("Only ZIP files are allowed.")

class BackupJob(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    apps = models.JSONField(default=list)
    include_media = models.BooleanField(default=True)
    include_db = models.BooleanField(default=True)

    def __str__(self):
        return f"Backup Job @ {self.created_at}"


class Backup(models.Model):
    file_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    drive_url = models.URLField(blank=True, null=True)
    backup_size = models.BigIntegerField(null=True, blank=True)

    def __str__(self):
        return self.file_name


class BackupUpload(models.Model):
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file = models.FileField(upload_to='uploaded_backups/', validators=[validate_zip])

    def __str__(self):
        return f"Backup uploaded on {self.uploaded_at}"
