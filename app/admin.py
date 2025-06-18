from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model
from django.urls import path, reverse
from django.utils.timezone import now
from django.shortcuts import render, redirect
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.http import HttpResponseRedirect

from .models import (
    UserProfile, Transaction, USDAccount, Fee, Region, 
    PlatformAccount, LinkedAccount, User, Alert, 
    HighRiskCountry, EmailTemplate, PromotionalEmail, ExchangeRate, UserPoints, PointTransaction, Reward
)
from kyc.models import KYCRequest
from .tasks import send_promotional_email
from drac.models import Anomaly, AuditLog, Reconciliation, ComplianceCheck
from drac.services import detect_anomalies, ReconciliationService, perform_compliance_check


from django.core.management import call_command
from django.contrib import messages

# Get the custom User model
User = get_user_model()


# ------------------ Promotional Email Admin ------------------
class PromotionalEmailAdmin(admin.ModelAdmin):
    list_display = ('subject', 'status', 'created_at', 'sent_at', 'send_now')
    search_fields = ('subject',)
    actions = ['send_selected_emails']

    def send_now(self, obj):
        if obj.status == "pending":
            url = reverse('admin:send_promotional_email', args=[obj.id])
            return format_html('<a class="button" href="{}">Send</a>', url)
        return "Sent"

    send_now.allow_tags = True
    send_now.short_description = "Send Now"
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('send-promotional-email/<int:pk>/', self.admin_site.admin_view(self.send_promotional_email), name='send_promotional_email'),
        ]
        return custom_urls + urls

    def send_promotional_email(self, request, pk):
        email = PromotionalEmail.objects.get(pk=pk)
        send_promotional_email.delay(email.id)  # Asynchronous task
        email.status = "sent"
        email.sent_at = now()
        email.save()
        messages.success(request, f"Promotional email '{email.subject}' is being sent.")
        return redirect('/admin/app/promotionalemail/')

# ------------------ Custom User Admin ------------------
class CustomUserAdmin(UserAdmin):
    list_display = ('id', 'username', 'email', 'is_active', 'is_staff', 'is_superuser')
    list_filter = ('is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'email')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('email',)}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'password1', 'password2'),
        }),
    )


# ------------------ Transaction Admin ------------------
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'amount', 'timestamp', 'status')
    search_fields = ('user__username', 'user__email', 'amount', 'status', 'id')
    actions = ['detect_anomalies_action', 'ReconciliationService_action']

    @admin.action(description=_('Detect Anomalies in Selected Transactions'))
    def detect_anomalies_action(self, request, queryset):
        transaction_amounts = queryset.values_list('amount', flat=True)
        anomalies = detect_anomalies(transaction_amounts)

        if anomalies:
            messages.warning(request, f"Detected {len(anomalies)} anomalies.")
        else:
            messages.success(request, "No anomalies detected.")

    @admin.action(description=_('Reconcile Transactions'))
    def ReconciliationService_action(self, request, queryset):
        success = ReconciliationService()

        if success:
            messages.success(request, "Reconciliation successful.")
        else:
            messages.error(request, "Discrepancies detected. Check logs for details.")

# ------------------ Other Model Admins ------------------
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'username', 'unique_id')
    search_fields = ('user__username', 'user__email', 'unique_id', 'username')
    list_filter = ('username', 'unique_id')
    actions = ['compliance_check_action']

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related('user') 

    @admin.action(description='Perform Compliance Check')
    def compliance_check_action(self, request, queryset):  # 'modeladmin' should be 'self'
        for transaction in queryset:
            user = transaction.user  # Assuming transaction.user is a User instance
        
            try:
                # Convert User to UserProfile
                user_profile = UserProfile.objects.get(user=user)
            except UserProfile.DoesNotExist:
                self.message_user(request, f"UserProfile not found for user {user.id}.", level='error')
                continue
        
            try:
                # Fetch the related KYCRequest
                kyc_request = KYCRequest.objects.get(user=user_profile)
            except KYCRequest.DoesNotExist:
                self.message_user(request, f"No KYC record found for user {user_profile.username}.", level='error')
                continue
        
            # Call your compliance check function
            result = perform_compliance_check(user_profile, kyc_request)  
        
            if result in ["UserProfile not found.", "KYC record not found."]:
                self.message_user(request, result, level='error')
            else:
                self.message_user(request, f"Compliance check completed for user {user.id}.", level='success')

@admin.register(USDAccount)
class USDAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'created_at')
    search_fields = ('user__username', 'user__email', 'account_id')

@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ['currency_code', 'rate_to_usd', 'last_updated']
    actions = ['update_rates_via_command']

    def update_rates_via_command(self, request, queryset):
        """Admin action to manually update rates."""
        try:
            call_command('update_rates')  # Calls your management command
            self.message_user(request, "Exchange rates updated successfully!", messages.SUCCESS)
        except Exception as e:
            self.message_user(request, f"Error: {str(e)}", messages.ERROR)
    update_rates_via_command.short_description = "Update selected currencies from API"

@admin.register(Fee)
class FeeAdmin(admin.ModelAdmin):
    list_display = ('transaction_type', 'is_active')
    search_fields = ('user__username',)

@admin.register(PlatformAccount)
class PlatformAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'balance', 'unique_id')
    search_fields = ('name', 'balance', 'unique_id')
    list_filter = ('name', 'balance')

@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')  
    search_fields = ('name',)  

@admin.register(LinkedAccount)
class LinkedAccountAdmin(admin.ModelAdmin):
    pass

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    pass

@admin.register(HighRiskCountry)
class HighRiskCountryAdmin(admin.ModelAdmin):
    pass


# ------------------ Email Template Admin ------------------
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'subject')
    search_fields = ('name', 'subject')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('email-preview/<int:pk>/', self.admin_site.admin_view(self.email_preview), name='email-preview'),
        ]
        return custom_urls + urls

    def email_preview(self, request, pk):
        template = EmailTemplate.objects.get(pk=pk)
        return render(request, 'emails/preview.html', {'html_content': template.html_content})




@admin.register(PointTransaction)
class PointTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'points', 'transaction_type', 'reason', 'created_at')
    list_filter = ('transaction_type',)
    search_fields = ('user__username', 'reason')
    readonly_fields = ('created_at',)

@admin.register(UserPoints)
class UserPointsAdmin(admin.ModelAdmin):
    list_display = ('user', 'points', 'daily_earned', 'weekly_earned', 'last_activity', 'last_reset')
    search_fields = ('user__username',)
    readonly_fields = ('last_activity', 'last_reset')
    actions = ['reset_points', 'reset_limits']
    
    def reset_points(self, request, queryset):
        """Admin action to reset user points"""
        for user_points in queryset:
            user_points.points = 0
            user_points.save()
        self.message_user(request, f"Reset points for {queryset.count()} users.")
    reset_points.short_description = "Reset total points to zero"
    
    def reset_limits(self, request, queryset):
        """Admin action to reset daily/weekly limits"""
        for user_points in queryset:
            user_points.daily_earned = 0
            user_points.weekly_earned = 0
            user_points.last_reset = now()
            user_points.save()
        self.message_user(request, f"Reset limits for {queryset.count()} users.")
    reset_limits.short_description = "Reset daily/weekly limits"
    
    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if not obj:  # Adding new record
            return fieldsets
        # For existing records, show limits information
        return (
            (None, {'fields': ('user', 'points')}),
            ('Limits Tracking', {
                'fields': ('daily_earned', 'weekly_earned', 'last_reset'),
                'description': f'Daily limit: {obj.DAILY_LIMIT}, Weekly limit: {obj.WEEKLY_LIMIT}'
            }),
            ('Activity', {
                'fields': ('last_activity',)
            })
        )
        
@admin.register(Reward)    
class Reward(admin.ModelAdmin):
    pass
    
# ------------------ Registering Admins ------------------
admin.site.register(EmailTemplate, EmailTemplateAdmin)
admin.site.register(PromotionalEmail, PromotionalEmailAdmin)
admin.site.register(User, CustomUserAdmin)
