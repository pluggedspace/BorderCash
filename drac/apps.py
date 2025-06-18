from django.apps import AppConfig

class DracConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'drac'

    def ready(self):
        import drac.signals
