from django.contrib import admin
from .models import TokenizedStock, UserInvestment, TransactionLog


@admin.register(TokenizedStock)
class TokenizedStockAdmin(admin.ModelAdmin):
    list_display = ('name', 'symbol', 'issuer_address', 'price', 'is_active')
    search_fields = ('name', 'symbol')

@admin.register(UserInvestment)
class UserInvestmentAdmin(admin.ModelAdmin):
    list_display = ('user', 'stock', 'amount_held', 'purchase_price', 'current_value')
    search_fields = ('user__username', 'stock__symbol')

@admin.register(TransactionLog)
class TransactionLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'stock', 'transaction_type', 'amount', 'price', 'total_cost', 'timestamp')
    search_fields = ('user__username', 'stock__symbol', 'transaction_type')
