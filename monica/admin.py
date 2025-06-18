from django.contrib import admin
from import_export.admin import ExportMixin, ImportMixin
from import_export.resources import ModelResource
from django.utils.text import slugify
from django.urls import reverse
from django.utils.html import format_html
from .models import FAQ, RefundLog, Dispute
from django.contrib import admin, messages

class FAQResource(ModelResource):
    class Meta:
        model = FAQ
        import_id_fields = ["question"]

@admin.register(FAQ)
class FAQAdmin(ImportMixin, ExportMixin, admin.ModelAdmin):
    resource_class = FAQResource
    list_display = ("question", "answer")
    search_fields = ("question",)

    
@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = ("user", "category", "status", "refund_status", "created_at")
    list_filter = ("status", "refund_status", "category")
    search_fields = ("user__username", "transaction_id", "category", "description")
    readonly_fields = ("created_at", "updated_at")

    actions = ["escalate_to_human_support"]

    def escalate_to_human_support(self, request, queryset):
        """ Admin action to manually escalate disputes """
        updated_count = queryset.update(status="escalated")
        self.message_user(request, f"{updated_count} disputes have been escalated to human support.")

    escalate_to_human_support.short_description = "Escalate selected disputes to human support"

    def has_add_permission(self, request):
        """ Prevent direct addition of disputes from admin """
        return False  # Disputes should be created via the API

    def has_delete_permission(self, request, obj=None):
        """ Allow deletion only if the dispute is pending or closed """
        if obj and obj.status in ["pending", "closed"]:
            return True
        return False

@admin.register(RefundLog)
class RefundLogAdmin(admin.ModelAdmin):
    list_display = ("user", "transaction", "refund_amount", "refund_date", "reason")
    search_fields = ("user__email", "transaction__transaction_id")
    list_filter = ("refund_date",)
