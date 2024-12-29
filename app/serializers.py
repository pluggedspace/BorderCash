from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from rest_framework import serializers

from .models import UserProfile, Transaction, USDAccount, Fee, Region, LinkedAccount

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'password')
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    region = serializers.PrimaryKeyRelatedField(queryset=Region.objects.all(), required=False)

    class Meta:
        model = UserProfile
        fields = ['phone_number', 'region', 'country']


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'user', 'amount', 'transaction_type', 'status',
                  'created_at']  # Ensure the field name is correct


class USDAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = USDAccount
        fields = ['user', 'balance']


class FeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fee
        fields = ['transaction_type', 'flat_fee', 'percentage_fee']


class LinkedAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = LinkedAccount
        fields = '__all__'
