from django.contrib import admin
from .models import Anomaly, ComplianceCheck, AuditLog, Reconciliation
from app.models import UserProfile


@admin.register(Anomaly)
class AnomalyAdmin(admin.ModelAdmin):
    list_display = ('transaction', 'description', 'status', 'detected_at')
    search_fields = ('transaction__id', 'description', 'status')
    list_filter = ('status', 'detected_at')

@admin.register(ComplianceCheck)
class ComplianceCheckAdmin(admin.ModelAdmin):
    list_display = ('user', 'kyc', 'result', 'checked_at')
    search_fields = ('user__user__username', 'result')  
    list_filter = ('result', 'checked_at')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.select_related('user__user')  
        return queryset

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user":
            kwargs["queryset"] = UserProfile.objects.all()  # Ensure the admin form shows UserProfile dropdown
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if isinstance(obj.user, User):  # If the admin tries to save a User instance
            try:
                obj.user = UserProfile.objects.get(user=obj.user)
            except UserProfile.DoesNotExist:
                raise ValueError("The selected user does not have a related UserProfile instance.")
        
        super().save_model(request, obj, form, change)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('transaction', 'description', 'status', 'audited_at')
    search_fields = ('transaction__id', 'description', 'status')
    list_filter = ('status', 'audited_at')


@admin.register(Reconciliation)
class ReconciliationAdmin(admin.ModelAdmin):
    list_display = ('transaction', 'expected_amount', 'actual_amount', 'status', 'reconciled_at')
    search_fields = ('transaction__id', 'status')
    list_filter = ('status', 'reconciled_at')
