from django.contrib import admin
from .models import UserProfile, Transaction, USDAccount, Fee, Region, PlatformAccount, LinkedAccount


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    pass


@admin.register(PlatformAccount)
class PlatformAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'balance', 'unique_id')
    search_fields = ('user__username',)
    list_filter = ('name', 'balance')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'username', 'unique_id')
    search_fields = ('user__username',)
    list_filter = ('username', 'unique_id')


@admin.register(USDAccount)
class USDAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'created_at')
    search_fields = ('transaction__transaction_type',)


@admin.register(Fee)
class FeeAdmin(admin.ModelAdmin):
    list_display = ('transaction_type', 'is_active')
    search_fields = ('user__username',)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'id', 'transaction_type', 'amount', 'status', 'created_at')
    search_fields = ('user__username', 'transaction_type')
    list_filter = ('transaction_type', 'status', 'created_at')

    pass


@admin.register(LinkedAccount)
class LinkedAccountAdmin(admin.ModelAdmin):
    pass



