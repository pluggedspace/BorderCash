from rest_framework import serializers
from .models import TokenizedStock, UserInvestment, TransactionLog, InvestmentAccount

class TokenizedStockSerializer(serializers.ModelSerializer):
    class Meta:
        model = TokenizedStock
        fields = '__all__'

class InvestmentAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvestmentAccount
        fields = '__all__'

class UserInvestmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserInvestment
        fields = '__all__'

class TransactionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = TransactionLog
        fields = '__all__'


