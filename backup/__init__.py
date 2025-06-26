from django.apps import AppConfig

class BackupConfig(AppConfig):
    name = 'backup'

    def ready(self):
        import backup.tasks  # noqa
