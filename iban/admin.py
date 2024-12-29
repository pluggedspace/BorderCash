from django.contrib import admin
from .models import IBANAccount, Card, Transaction, AuditLog, Notification


@admin.register(IBANAccount)
class IBANAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'iban_number', 'status', 'created_at', 'updated_at')
    search_fields = ('user__email', 'iban_number')
    list_filter = ('status',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Card)
class CardAdmin(admin.ModelAdmin):
    list_display = ('user', 'card_number', 'card_type', 'status', 'created_at', 'updated_at')
    search_fields = ('user__email', 'card_number')
    list_filter = ('status',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('iban_account', 'transaction_type', 'amount', 'created_at')
    search_fields = ('iban_account__iban_number', 'transaction_type')
    list_filter = ('transaction_type',)
    readonly_fields = ('created_at',)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'timestamp')
    search_fields = ('user__email', 'action')
    list_filter = ('timestamp',)
    readonly_fields = ('timestamp',)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'is_read', 'created_at')
    search_fields = ('user__email', 'message')
    list_filter = ('is_read',)
    readonly_fields = ('created_at',)
