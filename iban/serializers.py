from rest_framework import serializers
from .models import IBANAccount, Card, Transaction, Notification


class IBANAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = IBANAccount
        fields = ['id', 'iban_number', 'status', 'created_at', 'updated_at']


class CardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Card
        fields = ['id', 'card_number', 'card_type', 'status', 'created_at', 'updated_at']


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'iban_account', 'transaction_type', 'amount', 'created_at']


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'message', 'is_read', 'created_at']
