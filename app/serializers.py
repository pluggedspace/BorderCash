from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from rest_framework import serializers

from .models import UserProfile, Transaction, USDAccount, Fee, Region, LinkedAccount, UserPoints, PointTransaction, Notification, Reward

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
    email = serializers.EmailField(source='user.email', read_only=True)
    kyc_status = serializers.CharField(read_only=True)
    is_kyc_completed = serializers.BooleanField(read_only=True)
    latest_kyc_request = serializers.SerializerMethodField(read_only=True)
    has_transaction_pin = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = ['username', 'email', 'date_of_birth', 'full_name', 'phone_number', 'preferred_currency', 'city', 'state', 'country', 'region', 'kyc_status', 'is_kyc_completed', 'latest_kyc_request', 'has_transaction_pin']
        read_only_fields = ['unique_id']
    
    def create(self, validated_data):
        user = validated_data.pop('user')
        
        # Remove username from validated_data since we're setting it explicitly
        username = validated_data.pop('username', user.username)
        
        # Create the profile
        profile = UserProfile.objects.create(
            user=user,
            username=username,
            **validated_data
        )
        return profile

    def get_latest_kyc_request(self, obj):
        latest_kyc = obj.latest_kyc_request
        if latest_kyc:
            return {
                'status': latest_kyc.status,
                'created_at': latest_kyc.created_at,
            }
        return None

    def update(self, instance, validated_data):
        # Handle updates to the User object
        user_data = validated_data.pop('user', None)
        if user_data:
            user = instance.user
            for attr, value in user_data.items():
                setattr(user, attr, value)
            user.save()

        # Handle updates to the UserProfile object
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

    def get_has_transaction_pin(self, obj):
        return bool(obj.transaction_pin)


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'user', 'amount', 'transaction_type', 'status', 'initial_deposit_amount','operator_id', 'recipient_phone', 'description','transaction_id',
        'details', 'currency_from', 'payment_method', 'fee_amount', 'destination_account', 'created_at']  # Ensure the field name is correct


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


class UserPointsSerializer(serializers.ModelSerializer):
    """ Serializer for UserPoints model """

    class Meta:
        model = UserPoints
        fields = ['user', 'points', 'last_activity']
        read_only_fields = ['user', 'last_activity']  # Users cannot modify these

class PointTransactionSerializer(serializers.ModelSerializer):
    """ Serializer for PointTransaction model """

    class Meta:
        model = PointTransaction
        fields = ['user', 'points', 'transaction_type', 'reason', 'created_at']
        read_only_fields = ['user', 'created_at']
        

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'
        
        
class RewardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reward
        fields = '__all__'