import logging
import uuid
from decimal import Decimal
from email.message import EmailMessage

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction, IntegrityError
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django_countries import countries
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.views import TokenObtainPairView
from django.core.exceptions import ObjectDoesNotExist
from app.services.transact.transfer import TransferService, InsufficientFundsError
from . import serializers
from .models import Transaction, USDAccount, UserProfile, Region, LinkedAccount
from .serializers import UserSerializer, UserProfileSerializer, USDAccountSerializer, TransactionSerializer, \
    LinkedAccountSerializer
from .services.transact.deposit import DepositService
from .services.transact.withdrawal import WithdrawalService

logger = logging.getLogger(__name__)


def get_country_code(country_name):
    for code, name in dict(countries).items():
        if name.lower() == country_name.lower():
            return code
    return None


# Registration
@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    try:
        with transaction.atomic():
            user_data = {
                'username': request.data.get('username'),
                'email': request.data.get('email'),
                'password': request.data.get('password')
            }
            profile_data = request.data.get('profile', {})

            logger.info(f"Incoming registration data: {user_data}")

            # Validate and create user
            user_serializer = UserSerializer(data=user_data)
            if not user_serializer.is_valid():
                logger.error(f"User serializer errors: {user_serializer.errors}")
                return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            user = user_serializer.save()

            # Handle region
            region_name = profile_data.get('region')
            if region_name:
                try:
                    region = Region.objects.get(name=region_name)
                    profile_data['region'] = region.id
                except Region.DoesNotExist:
                    user.delete()  # Rollback user creation
                    return Response({"error": f"Invalid region: {region_name}"}, status=status.HTTP_400_BAD_REQUEST)

            # Handle country
            country_name = profile_data.get('country')
            if country_name:
                country_code = get_country_code(country_name)
                if country_code:
                    profile_data['country'] = country_code
                else:
                    user.delete()  # Rollback user creation
                    return Response({"error": f"Invalid country: {country_name}"}, status=status.HTTP_400_BAD_REQUEST)

            # Validate profile data
            profile_serializer = UserProfileSerializer(data=profile_data)
            if not profile_serializer.is_valid():
                logger.error(f"Profile serializer errors: {profile_serializer.errors}")
                user.delete()  # Rollback user creation
                return Response(profile_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Create UserProfile
            profile = profile_serializer.save(user=user)

            # Create USD account
            usd_account = USDAccount.objects.create(user=user, balance=0.0)

            return Response({
                'user': UserSerializer(user).data,
                'profile': UserProfileSerializer(profile).data,
                'usd_account': {'id': usd_account.id, 'balance': usd_account.balance},
            }, status=status.HTTP_201_CREATED)

    except IntegrityError as e:
        logger.error(f"IntegrityError during user registration: {str(e)}")
        return Response({'error': 'A unique constraint error occurred'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Unexpected error during user registration: {str(e)}")
        return Response({'error': 'An unexpected error occurred'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Helper function for email verification (optional)
def send_verification_email(request, user):
    current_site = get_current_site(request)
    mail_subject = 'Activate your account.'
    message = render_to_string('acc_active_email.html', {
        'user': user,
        'domain': current_site.domain,
        'uid': urlsafe_base64_encode(force_bytes(user.pk)),
        # No activation token needed anymore
    })
    email = EmailMessage(mail_subject, message, to=[user.email])
    email.send()


def validate_user_data(data):
    if User.objects.filter(email=data['email']).exists():
        raise serializers.ValidationError("A user with this email already exists.")

    try:
        validate_password(data['password'])
    except ValidationError as e:
        raise serializers.ValidationError({"password": list(e.messages)})


# Login
class LoginView(TokenObtainPairView):
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = TokenObtainPairSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# Logout
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Logout a user by blacklisting the token."""
    try:
        # Get the token from the request
        token = request.auth
        # Blacklist the token
        BlacklistedToken.objects.create(token=token)
        return Response({"message": "Logged out successfully."}, status=status.HTTP_204_NO_CONTENT)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


# Reset Auth
@api_view(['POST'])
def password_reset_request(request):
    email = request.data.get("email")
    if not email:
        return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"error": "User with this email does not exist"}, status=status.HTTP_404_NOT_FOUND)

    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    reset_link = f"http://yourfrontend.com/reset-password/{uid}/{token}/"  # Adjust based on your frontend
    message = render_to_string('password_reset_email.html', {'reset_link': reset_link})

    send_mail(
        'Password Reset Request',
        message,
        'no-reply@yourdomain.com',  # Replace with your email
        [email],
        fail_silently=False,
    )

    return Response({"message": "Password reset email sent"}, status=status.HTTP_200_OK)


@api_view(['POST'])
def password_reset_confirm(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        new_password = request.data.get("new_password")
        if not new_password:
            return Response({"error": "New password is required"}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({"message": "Password has been reset successfully"}, status=status.HTTP_200_OK)

    return Response({"error": "Invalid token or user ID"}, status=status.HTTP_400_BAD_REQUEST)


# Account
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def account_view(request):
    """Retrieve the user's account details."""
    user = request.user
    usd_account = get_object_or_404(USDAccount, user=user)
    return Response(USDAccountSerializer(usd_account).data, status=status.HTTP_200_OK)


# Balance
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def balance_view(request):
    """Retrieve the user's USD balance."""
    user = request.user
    usd_account = get_object_or_404(USDAccount, user=user)
    return Response({'balance': usd_account.balance}, status=status.HTTP_200_OK)


# Transaction History
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transaction_view(request):
    """Retrieve a list of transactions for the user."""
    user = request.user
    transactions = Transaction.objects.filter(user=user).order_by('-created_at')
    serializer = TransactionSerializer(transactions, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# Deposit
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_deposit(request):
    try:
        user = request.user
        gateway = request.data.get("gateway")
        amount = request.data.get("amount")
        from_currency = request.data.get("from_currency")

        amount = Decimal(amount)

        # Validate deposit amount
        if not amount or Decimal(amount) <= 0:
            return Response({"status": "error", "message": "Invalid deposit amount."},
                            status=status.HTTP_400_BAD_REQUEST)

        deposit_service = DepositService(user)

        # Handle deposit initiation based on the selected method
        if gateway == "usdcxlm":
            instructions, deposit_id = deposit_service.initiate_usdc_deposit(amount)
            return Response({"status": "success", "message": "USDC deposit initiated.", "instructions": instructions,
                             "deposit_id": deposit_id})

        elif gateway == "cryptoSwap":

            # Debug print to confirm values

            print(f"Request User: {request.user}, From Currency: {from_currency}, Amount: {amount}")

            # Call the Changelly deposit function

            result = deposit_service.deposit_to_usdc(request, from_currency, amount)

            # Log the result for debugging

            print(f"Deposit Result: {result}")

            # Check if the result indicates an error

            if 'error' in result:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)

            # Return a success response with the result

            return Response(result, status=status.HTTP_200_OK)

        elif gateway == "link":
            deposit_response = deposit_service.initiate_link_deposit(amount, currency=from_currency, request=request)
            if deposit_response:
                return Response({
                    "status": "success",
                    "message": "Make your payment to this Link vendor.",
                    "payment_details": deposit_response
                })
            return Response({"status": "error", "message": "Link deposit not found or failed."},
                            status=status.HTTP_400_BAD_REQUEST)

        return Response({"status": "error", "message": "Invalid deposit method."},
                        status=status.HTTP_400_BAD_REQUEST)

    except UserProfile.DoesNotExist:
        logger.error("UserProfile does not exist for user ID: {}".format(user.id))
        return Response({"status": "error", "message": "User profile does not exist."},
                        status=status.HTTP_404_NOT_FOUND)
    except ValueError as e:
        logger.error(f"ValueError occurred: {str(e)}", exc_info=True)
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Transaction.DoesNotExist as e:
        logger.error(f"Transaction does not exist: {str(e)}", exc_info=True)
        return Response({"status": "error", "message": "Transaction not found."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}", exc_info=True)
        return Response({"status": "error", "message": f"An unexpected error occurred: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Withdraw
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_withdrawal(request):
    try:
        user = request.user
        gateway = request.data.get("gateway")
        amount = request.data.get("amount")
        destination_account = request.data.get("destination_account")

        # Validate withdrawal amount
        if not amount or Decimal(amount) <= 0:
            return Response({"status": "error", "message": "Invalid withdrawal amount."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Generate a unique transaction ID
        transaction_id = str(uuid.uuid4())

        withdraw_service = WithdrawalService(user)

        # Handle withdrawal initiation based on the selected method
        if gateway == "usdc":
            destination_account = request.data.get("destination_account")
            instructions = withdraw_service.withdraw_stellar(amount, destination_account, transaction_id)

            # Check the response from the withdraw_stellar method
            if instructions.get("success"):
                return Response({"status": "success", "message": "USDC withdrawal initiated.",
                                 "transaction_hash": instructions["transaction_hash"],
                                 "transaction_id": transaction_id})  # Include transaction ID in the response
            else:
                return Response({"status": "error", "message": instructions.get("error", "Withdrawal failed.")})

        elif gateway == "crypto":
            target_currency = request.data.get("target_currency")
            from_currency = "USDCXLM"
            result = withdraw_service.process_crypto(amount, from_currency, target_currency, destination_account)

            # Log the result for debugging
            logger.info(f"Changelly Withdrawal Result: {result}")

            # Check if the result indicates an error
            if 'error' in result:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)

            # Return a success response with the result
            return Response(result, status=status.HTTP_200_OK)

        elif gateway == "link":
            currency = request.data.get("currency")
            bank_name = request.data.get("bank_name")
            account_name = request.data.get("account_name")
            account_number = request.data.get("account_number")

            try:
                # Pass the authenticated user to the service method
                withdraw_response = withdraw_service.initiate_offramp_transaction(amount=amount, currency=currency,
                                                                                  account_name=account_name,
                                                                                  account_number=account_number,
                                                                                  bank_name=bank_name,
                                                                                  request_user=user)

                if withdraw_response:
                    return Response({
                        "status": "success",
                        "message": "Payment via Link in progress.",
                        "payment_details": withdraw_response
                    })

                # Log the error if response is empty or failed
                logger.error("Link.io returned an empty response or failed for amount: %s", amount)
                return Response({"status": "error", "message": "Link deposit not found or failed."},
                                status=status.HTTP_502_BAD_GATEWAY)
            except Exception as e:
                logger.exception("Error during Link.io off-ramp transaction")
                return Response({"status": "error", "message": "An error occurred: " + str(e)},
                                status=status.HTTP_502_BAD_GATEWAY)

        return Response({"status": "error", "message": "Invalid withdrawal method."},
                        status=status.HTTP_400_BAD_REQUEST)

    except ValueError as e:
        logger.error(f"ValueError occurred: {str(e)}", exc_info=True)
        return Response({"status": "error", "message": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Transaction.DoesNotExist as e:
        logger.error(f"Transaction does not exist: {str(e)}", exc_info=True)
        return Response({"status": "error", "message": "Transaction not found."}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Unexpected error occurred: {str(e)}", exc_info=True)
        return Response({"status": "error", "message": f"An unexpected error occurred: {str(e)}"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Webhook for withdrawal confirmation
@api_view(['POST'])
def withdrawal_webhook(request):
    withdrawal_info = request.data
    ledger_entry = Transaction.objects.get(transaction_type="withdrawal", status="pending")
    ledger_entry.status = "completed"
    ledger_entry.save()

    return Response({"message": "Withdrawal confirmed."}, status=200)


# Transfers
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_transfer(request):
    sender = request.user
    recipient_username = request.data.get("recipient")
    amount = request.data.get("amount")

    try:
        amount = float(amount)  # Ensure amount is a float for validation
    except (ValueError, TypeError):
        return Response({"error": "Invalid amount."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        User = get_user_model()
        recipient = User.objects.get(username=recipient_username)
    except User.DoesNotExist:
        return Response({"error": "Recipient not found."}, status=status.HTTP_404_NOT_FOUND)

    transfer_service = TransferService()

    try:
        result = transfer_service.process_internal_transfer(sender, recipient, amount)

        if "error" in result:
            return Response({"error": result["error"]}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": "Transfer successful"}, status=status.HTTP_200_OK)

    except ValueError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except InsufficientFundsError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Unexpected error during transfer: {e}")
        return Response({"error": "An unexpected error occurred."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Service Status
@api_view(['GET'])
def health_check(request):
    """Check the health of the service."""
    return Response({"status": "healthy"}, status=status.HTTP_200_OK)


class LinkedAccountView(APIView):
    def post(self, request):
        """
        Create and link a bank account to Circle.
        """
        serializer = LinkedAccountSerializer(data=request.data)
        if serializer.is_valid():
            linked_account = serializer.save()  # Create and save the LinkedAccount instance

            # Call the `link_account_to_circle` method to link the account with Circle
            try:
                circle_id = linked_account.link_account_to_circle()  # The method returns the Circle ID
                return Response({'circle_id': circle_id}, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, pk):
        """
        Fetch and cross-match Circle ID with an existing account.
        """
        try:
            linked_account = LinkedAccount.objects.get(pk=pk)
            circle_id = linked_account.fetch_and_cross_match_circle_id()
            if circle_id:
                return Response({'circle_id': circle_id}, status=status.HTTP_200_OK)
            return Response({'message': 'No matching Circle account found.'}, status=status.HTTP_404_NOT_FOUND)
        except LinkedAccount.DoesNotExist:
            return Response({'error': 'Account not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
