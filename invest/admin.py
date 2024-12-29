import uuid

from django.contrib import admin
from .models import TradingAccount, PortfolioAllocation, TransactionHistory, TradeHistory


# TradingAccount Admin
@admin.register(TradingAccount)
class TradingAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "alpaca_tag", "virtual_balance", "created_at")
    search_fields = ("user__username", "alpaca_tag")
    list_filter = ("created_at",)
    readonly_fields = ("alpaca_tag",)  # Make alpaca_tag readonly since it's auto-generated

    def save_model(self, request, obj, form, change):
        """Override save to handle the alpaca_tag"""
        if not obj.alpaca_tag:
            obj.alpaca_tag = str(uuid.uuid4())  # Generate alpaca_tag if not already set
        super().save_model(request, obj, form, change)


# PortfolioAllocation Admin
@admin.register(PortfolioAllocation)
class PortfolioAllocationAdmin(admin.ModelAdmin):
    list_display = ("user", "symbol", "quantity", "avg_price", "updated_at")
    search_fields = ("user__username", "symbol")
    list_filter = ("updated_at",)
    ordering = ("user", "symbol")


# TransactionHistory Admin
@admin.register(TransactionHistory)
class TransactionHistoryAdmin(admin.ModelAdmin):
    list_display = ("user", "symbol", "transaction_type", "quantity", "price", "status", "created_at")
    search_fields = ("user__username", "symbol", "transaction_type")
    list_filter = ("status", "transaction_type", "created_at")
    ordering = ("-created_at",)  # Order by latest first


# TradeHistory Admin
@admin.register(TradeHistory)
class TradeHistoryAdmin(admin.ModelAdmin):
    list_display = ("user", "stock_symbol", "quantity", "purchase_price", "purchase_timestamp")
    search_fields = ("user__username", "stock_symbol")
    list_filter = ("purchase_timestamp",)
    ordering = ("-purchase_timestamp",)  # Order by latest first
