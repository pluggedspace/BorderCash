from django.contrib import admin
from .models import Product, Order, ShoppingFee

admin.site.register(Product)
admin.site.register(ShoppingFee)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "product", "total_cost", "order_status")
    list_filter = ("order_status", "total_cost")
    search_fields = ("user__username", "product__name")
    actions = ["mark_as_shipped", "mark_as_delivered"]

    def mark_as_shipped(self, request, queryset):
        queryset.update(order_status="Shipped")

    mark_as_shipped.short_description = "Mark selected orders as shipped"

    def mark_as_delivered(self, request, queryset):
        queryset.update(order_status="Delivered")

    mark_as_delivered.short_description = "Mark selected orders as delivered"
