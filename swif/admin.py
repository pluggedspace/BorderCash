from django_celery_beat.admin import PeriodicTaskAdmin, PeriodicTaskForm
from django_celery_beat.models import PeriodicTask
from django.contrib import admin

class CustomPeriodicTaskForm(PeriodicTaskForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Customize the task dropdown if needed
        self.fields['task'].widget.attrs.update({'class': 'custom-class'})

@admin.register(PeriodicTask)
class CustomPeriodicTaskAdmin(PeriodicTaskAdmin):
    form = CustomPeriodicTaskForm
    list_display = ('name', 'task', 'enabled', 'interval', 'start_time')