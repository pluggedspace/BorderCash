from rest_framework import serializers
from .models import TransactionHistory, PortfolioAllocation, TradeHistory


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionHistory
        fields = ['id', 'user', 'symbol', 'transaction_type', 'quantity', 'price', 'status', 'created_at']


class PortfolioAllocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PortfolioAllocation
        fields = ['user', 'symbol', 'quantity', 'avg_price']


class TradeHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TradeHistory
        fields = ['user', 'stock_symbol', 'quantity', 'purchase_price', 'purchase_timestamp']
