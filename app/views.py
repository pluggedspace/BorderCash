# Standard library
import logging
import random
import uuid
from datetime import datetime
from decimal import Decimal
from email.message import EmailMessage

# Django core
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sites.models import Site
from django.contrib.sites.shortcuts import get_current_site
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

# Third-party
from django_countries import countries
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.views import TokenObtainPairView

# Local apps - utils & services
from app.services.transact.deposit import DepositService
from app.services.transact.transfer import InsufficientFundsError, TransferService
from app.services.transact.withdrawal import WithdrawalService
from app.utils.currency import convert_usd_to_local
from app.utils.mail import send_email

# Local apps - models & serializers
from . import serializers
from .models import (
    LinkedAccount, Notification, PointTransaction, Referral, Region,
    Transaction, USDAccount, User, UserPoints, UserProfile, Reward
)
from .serializers import (
    LinkedAccountSerializer, NotificationSerializer, PointTransactionSerializer,
    TransactionSerializer, USDAccountSerializer, UserPointsSerializer,
    UserProfileSerializer, RewardSerializer, UserSerializer
)



from django.utils import timezone
from django.shortcuts import redirect


User = get_user_model()



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
            # Extract and validate input data
            user_data = {
                'username': request.data.get('username'),
                'email': request.data.get('email').lower() if request.data.get('email') else None,
                'password': request.data.get('password')
            }
            
            profile_data = request.data.get('profile', {})
            profile_data['username'] = user_data['username']
            referral_code = request.data.get('referral_code')

            logger.info(f"New registration attempt for username: {user_data.get('username')}")

            # Validate required fields
            if not all(user_data.values()):
                missing = [k for k, v in user_data.items() if not v]
                logger.warning(f"Missing required fields: {missing}")
                return Response(
                    {"error": f"Missing required fields: {', '.join(missing)}"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check for existing user
            if User.objects.filter(username__iexact=user_data['username']).exists():
                logger.warning(f"Username {user_data['username']} already exists")
                return Response(
                    {"error": "Username already taken"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if User.objects.filter(email__iexact=user_data['email']).exists():
                logger.warning(f"Email {user_data['email']} already registered")
                return Response(
                    {"error": "Email already registered"}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate user data
            user_serializer = UserSerializer(data=user_data)
            if not user_serializer.is_valid():
                logger.error(f"User validation failed: {user_serializer.errors}")
                return Response(
                    user_serializer.errors, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create user and generate verification token
            user = user_serializer.save()
            verification_token = user.generate_verification_token()
            logger.info(f"Generated verification token for user {user.id}")

            # Send verification email
            try:
                send_verification_email(request, user)
                email_status = "Verification email sent"
            except Exception as e:
                logger.error(f"Failed to send verification email: {str(e)}")
                email_status = "Account created but verification email failed"

            # Handle referral
            if referral_code:
                try:
                    referrer = User.objects.get(referral_code=referral_code)
                    Referral.objects.create(
                        referrer=referrer,
                        referred_user=user,
                        status='approved'
                    )
                    logger.info(f"Referral recorded: {referrer.id} -> {user.id}")
                except User.DoesNotExist:
                    logger.warning(f"Invalid referral code: {referral_code}")

            # Process profile data
            region_name = profile_data.get('region')
            if region_name:
                try:
                    region = Region.objects.get(name__iexact=region_name)
                    profile_data['region'] = region.id
                except Region.DoesNotExist:
                    logger.warning(f"Invalid region: {region_name}")
                    return Response(
                        {"error": f"Invalid region: {region_name}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            country_name = profile_data.get('country')
            if country_name:
                country_code = get_country_code(country_name)
                if country_code:
                    profile_data['country'] = country_code
                else:
                    logger.warning(f"Invalid country: {country_name}")
                    return Response(
                        {"error": f"Invalid country: {country_name}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Create profile
            profile_serializer = UserProfileSerializer(data=profile_data)
            if not profile_serializer.is_valid():
                logger.error(f"Profile validation failed: {profile_serializer.errors}")
                return Response(
                    profile_serializer.errors,
                    status=status.HTTP_400_BAD_REQUEST
                )
            profile = profile_serializer.save(user=user)

            # Create default USD account
            usd_account = USDAccount.objects.create(user=user, balance=0.0)

            # Prepare success response
            response_data = {
                'user': UserSerializer(user).data,
                'profile': UserProfileSerializer(profile).data,
                'usd_account': {
                    'id': usd_account.id,
                    'balance': usd_account.balance
                },
                'message': f"Registration successful. {email_status}"
            }

            logger.info(f"User {user.id} registered successfully")
            return Response(response_data, status=status.HTTP_201_CREATED)

    except IntegrityError as e:
        logger.error(f"Database integrity error: {str(e)}")
        return Response(
            {"error": "Registration failed due to database conflict"},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Unexpected registration error: {str(e)}", exc_info=True)
        return Response(
            {"error": "An unexpected error occurred during registration"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
# Helper function for email verification (optional)
def send_verification_email(request, user):
    """
    Sends account verification email using custom ZeptoMail integration
    """
    verification_link = request.build_absolute_uri(
        reverse('verify-email', kwargs={'token': user.email_verification_token}))
    
    context = {
        'user': user,
        'verification_link': verification_link,
        'username': user.username,
        'support_email': settings.SUPPORT_EMAIL,
        'app_name': settings.APP_NAME,
    }

    try:
        send_email(
            subject=f"Verify your {settings.APP_NAME} account",
            recipient=user.email,
            template_name='email_verification',
            context=context
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send verification email to {user.email}: {str(e)}")
        return False
        
def validate_user_data(data):
    if User.objects.filter(email=data['email']).exists():
        raise serializers.ValidationError("A user with this email already exists.")

    try:
        validate_password(data['password'])
    except ValidationError as e:
        raise serializers.ValidationError({"password": list(e.messages)})


@api_view(['GET'])
def verify_email(request, token):
    try:
        if not token or len(token) < 10:  # Basic token validation
            logger.error("Invalid token format received")
            return Response(
                {"error": "Invalid verification link format"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(email_verification_token=token)
        except User.DoesNotExist:
            logger.error(f"Token not found in database: {token[:8]}...")
            return Response(
                {"error": "Invalid verification link. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check expiration
        if (user.verification_token_expires and 
            user.verification_token_expires < timezone.now()):
            logger.warning(f"Expired token for user {user.id}")
            return Response(
                {"error": "Verification link has expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if user.is_verified:
            logger.info(f"User {user.id} already verified")
            return redirect(f"{settings.FRONTEND_URL}/already-verified?email={user.email}")

        # Use the model method to safely clear tokens
        user.clear_verification_token()
        
        logger.info(f"Successfully verified user {user.id}")
        return redirect(f"{settings.FRONTEND_URL}/verification-success?email={user.email}")

    except Exception as e:
        logger.error(f"Verification error: {str(e)}", exc_info=True)
        return Response(
            {"error": "An unexpected error occurred during verification."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_referral_code(request):
    return Response({
        'referral_code': request.user.referral_code,
        'referral_link': f"https://border.cash/register?ref={request.user.referral_code}"
    })
    
# Login
class LoginView(TokenObtainPairView):
    permission_classes = (AllowAny,)

    def post(self, request, *args, **kwargs):
        serializer = TokenObtainPairSerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            
            # Get the user from validated data
            user = serializer.user
            
            # Send login alert email
            try:
                send_email(
                    subject="New Login Alert",
                    recipient=user.email,
                    template_name="login_alert",  # Make sure you have this template
                    context={
                        'username': user.username,
                        'email': user.email,
                        'login_time': timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                        # Add any other context variables you need in the template
                    }
                )
            except Exception as email_error:
                # Log email error but don't fail the login
                print(f"Failed to send login alert email: {str(email_error)}")
            
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

    # Generate UID and token
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    # Dynamic domain retrieval
    current_site = Site.objects.get_current().domain
    reset_link = f"https://{current_site}/password-reset-confirm/{uid}/{token}/"

    # Render HTML email template
    email_content = render_to_string('password_reset_email.html', {'reset_link': reset_link})

    # Send email using ZeptoMail API
    subject = "Password Reset Request"
    send_email(email, subject, email_content)

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

# Set Pin
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_transaction_pin(request):
    try:
        user = request.user
        user_profile, created = UserProfile.objects.get_or_create(user=user)

        new_pin = request.data.get("new_pin")
        confirm_pin = request.data.get("confirm_pin")

        if not new_pin or not confirm_pin:
            return Response({"status": "error", "message": "PIN and confirmation PIN are required."},
                            status=status.HTTP_400_BAD_REQUEST)

        if new_pin != confirm_pin:
            return Response({"status": "error", "message": "PINs do not match."},
                            status=status.HTTP_400_BAD_REQUEST)

        user_profile.set_transaction_pin(new_pin)

        return Response({"status": "success", "message": "Transaction PIN set successfully."})

    except Exception as e:
        logger.error(f"Error setting transaction PIN: {str(e)}", exc_info=True)
        return Response({"status": "error", "message": "An unexpected error occurred."},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Account
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def account_view(request):
    user = request.user
    usd_account = get_object_or_404(USDAccount, user=user)
    profile = get_object_or_404(UserProfile, user=user)
    
    local_balance, rate = convert_usd_to_local(usd_account.balance, profile.preferred_currency)

    response_data = USDAccountSerializer(usd_account).data
    response_data.update({
        "local_currency": profile.preferred_currency,
        "local_balance": local_balance,
        "exchange_rate": rate,
    })

    return Response(response_data, status=status.HTTP_200_OK)

# Profile
class UserProfileAndAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            user = request.user
            user_profile = UserProfile.objects.get(user=user)
            user_profile_data = UserProfileSerializer(user_profile).data

            usd_account = USDAccount.objects.get(user=user)
            usd_account_data = USDAccountSerializer(usd_account).data

            local_balance, rate = convert_usd_to_local(
                usd_account.balance, user_profile.preferred_currency
            )

            usd_account_data.update({
                "local_currency": user_profile.preferred_currency,
                "local_balance": local_balance,
                "exchange_rate": rate,
            })

            return Response({
                'user_profile': user_profile_data,
                'usd_account': usd_account_data
            })

        except UserProfile.DoesNotExist:
            raise NotFound("UserProfile not found")
        except USDAccount.DoesNotExist:
            raise NotFound("USDAccount not found")
            
#EditProfile
class EditUserProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        """Update user profile details."""
        try:
            profile = request.user.userprofile
            serializer = UserProfileSerializer(profile, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except UserProfile.DoesNotExist:
            return Response({'error': 'Profile not found'}, status=status.HTTP_404_NOT_FOUND)

# Balance
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def balance_view(request):
    user = request.user
    usd_account = get_object_or_404(USDAccount, user=user)
    profile = get_object_or_404(UserProfile, user=user)

    local_balance, rate = convert_usd_to_local(usd_account.balance, profile.preferred_currency)

    return Response({
        'balance': usd_account.balance,
        'local_currency': profile.preferred_currency,
        'local_balance': local_balance,
        'exchange_rate': rate
    }, status=status.HTTP_200_OK)
    
    
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
            response_data = {
                "status": "success", 
                "message": "USDC deposit initiated.", 
                "instructions": instructions,
                "deposit_id": deposit_id
            }
            
            # Send deposit initiation email
            try:
                send_email(
                    subject="Deposit Initiated - USDC",
                    recipient=user.email,
                    template_name="deposit_initiated",
                    context={
                        'username': user.username,
                        'amount': amount,
                        'currency': 'USDC',
                        'gateway': 'Stellar',
                        'date': timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'deposit_id': deposit_id,
                    }
                )
            except Exception as email_error:
                logger.error(f"Failed to send deposit initiation email: {str(email_error)}")

            return Response(response_data)

        elif gateway == "cryptoSwap":
            print(f"Request User: {request.user}, From Currency: {from_currency}, Amount: {amount}")
            result = deposit_service.deposit_to_usdc(request, from_currency, amount)
            print(f"Deposit Result: {result}")

            if 'error' in result:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)

            # Send deposit initiation email for crypto swap
            try:
                send_email(
                    subject="Deposit Initiated - Crypto Swap",
                    recipient=user.email,
                    template_name="deposit_initiated",
                    context={
                        'username': user.username,
                        'amount': amount,
                        'currency': from_currency,
                        'gateway': 'Crypto Swap',
                        'date': timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'deposit_id': result.get('id', 'N/A'),
                    }
                )
            except Exception as email_error:
                logger.error(f"Failed to send crypto swap deposit email: {str(email_error)}")

            return Response(result, status=status.HTTP_200_OK)

        elif gateway == "link":
            deposit_response = deposit_service.initiate_link_deposit(amount, currency=from_currency, request=request)
            if deposit_response:
                # Send deposit initiation email for Link
                try:
                    send_email(
                        subject="Deposit Initiated - Link",
                        recipient=user.email,
                        template_name="deposit_initiated",
                        context={
                            'username': user.username,
                            'amount': amount,
                            'currency': from_currency,
                            'gateway': 'Link',
                            'date': timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'payment_details': deposit_response,
                        }
                    )
                except Exception as email_error:
                    logger.error(f"Failed to send Link deposit email: {str(email_error)}")

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

        # Fetch the user's profile
        user_profile = UserProfile.objects.get(user=user)

        # Check if the user's KYC is verified
        if not user_profile.is_kyc_completed:
            return Response({"status": "error", "message": "KYC verification required for withdrawals."},
                            status=status.HTTP_403_FORBIDDEN)

        # Check if transaction PIN is set
        if not user_profile.transaction_pin:
            return Response({"status": "error", "message": "Transaction PIN not set. Please set up a PIN before withdrawing."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Verify transaction PIN
        transaction_pin = request.data.get("transaction_pin")
        if not transaction_pin or not user_profile.verify_transaction_pin(transaction_pin):
            return Response({"status": "error", "message": "Invalid transaction PIN."},
                            status=status.HTTP_403_FORBIDDEN)

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
                # Send withdrawal confirmation email
                try:
                    send_email(
                        subject="Withdrawal Initiated - USDC",
                        recipient=user.email,
                        template_name="withdrawal_initiated",
                        context={
                            'username': user.username,
                            'amount': amount,
                            'currency': 'USDC',
                            'date': timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'transaction_id': transaction_id,
                            'destination': destination_account,
                            'status': 'Pending'
                        }
                    )
                except Exception as email_error:
                    logger.error(f"Failed to send USDC withdrawal email: {str(email_error)}")

                return Response({
                    "status": "success", 
                    "message": "USDC withdrawal initiated.",
                    "transaction_hash": instructions["transaction_hash"],
                    "transaction_id": transaction_id
                })
            else:
                return Response({"status": "error", "message": instructions.get("error", "Withdrawal failed.")})

        elif gateway == "crypto":
            target_currency = request.data.get("target_currency")
            from_currency = "USDCXLM"
            result = withdraw_service.process_crypto(amount, from_currency, target_currency, destination_account)

            logger.info(f"Changelly Withdrawal Result: {result}")

            if 'error' in result:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)

            # Send withdrawal confirmation email for crypto
            try:
                send_email(
                    subject=f"Withdrawal Initiated - {target_currency}",
                    recipient=user.email,
                    template_name="withdrawal_initiated",
                    context={
                        'username': user.username,
                        'amount': amount,
                        'currency': target_currency,
                        'date': timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'transaction_id': result.get('id', 'N/A'),
                        'destination': destination_account,
                        'status': 'Pending'
                    }
                )
            except Exception as email_error:
                logger.error(f"Failed to send crypto withdrawal email: {str(email_error)}")

            return Response(result, status=status.HTTP_200_OK)

        elif gateway == "link":
            currency = request.data.get("currency")
            bank_name = request.data.get("bank_name")
            account_name = request.data.get("account_name")
            account_number = request.data.get("account_number")

            try:
                withdraw_response = withdraw_service.initiate_offramp_transaction(
                    amount=amount, 
                    currency=currency,
                    account_name=account_name,
                    account_number=account_number,
                    bank_name=bank_name,
                    request_user=user
                )

                if withdraw_response:
                    # Send withdrawal confirmation email for Link
                    try:
                        send_email(
                            subject="Withdrawal Initiated - Bank Transfer",
                            recipient=user.email,
                            template_name="withdrawal_initiated",
                            context={
                                'username': user.username,
                                'amount': amount,
                                'currency': currency,
                                'date': timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                                'bank_name': bank_name,
                                'account_number': account_number,
                                'status': 'Pending'
                            }
                        )
                    except Exception as email_error:
                        logger.error(f"Failed to send Link withdrawal email: {str(email_error)}")

                    return Response({
                        "status": "success",
                        "message": "Payment via Link in progress.",
                        "payment_details": withdraw_response
                    })

                logger.error("Link.io returned an empty response or failed for amount: %s", amount)
                return Response({"status": "error", "message": "Link deposit not found or failed."},
                                status=status.HTTP_502_BAD_GATEWAY)
            except Exception as e:
                logger.exception("Error during Link.io off-ramp transaction")
                return Response({"status": "error", "message": "An error occurred: " + str(e)},
                                status=status.HTTP_502_BAD_GATEWAY)

        return Response({"status": "error", "message": "Invalid withdrawal method."},
                        status=status.HTTP_400_BAD_REQUEST)

    except UserProfile.DoesNotExist:
        return Response({"status": "error", "message": "User profile not found."},
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
        amount = float(amount)
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

        # Send emails to both sender and recipient
        try:
            # Email to sender
            send_email(
                subject="Transfer Sent",
                recipient=sender.email,
                template_name="transfer_sent",
                context={
                    'username': sender.username,
                    'amount': amount,
                    'recipient': recipient.username,
                    'date': timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'transaction_id': result.get('transaction_id', 'N/A')
                }
            )
            
            # Email to recipient
            send_email(
                subject="Transfer Received",
                recipient=recipient.email,
                template_name="transfer_received",
                context={
                    'username': recipient.username,
                    'amount': amount,
                    'sender': sender.username,
                    'date': timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'transaction_id': result.get('transaction_id', 'N/A')
                }
            )
        except Exception as email_error:
            logger.error(f"Failed to send transfer emails: {str(email_error)}")

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
    """
    Linked Account API Endpoints:
    - POST /link-account/: Create new linked account
    - GET /linked-account/<pk>/: Retrieve specific linked account
    """
    
    def post(self, request):
        """Create new linked account"""
        serializer = LinkedAccountSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            account = serializer.save()
            return Response(
                {
                    'id': account.id,
                    'bank_name': account.bank_name,
                    'account_number': f"••••{account.account_number[-4:]}",
                    'default': account.default
                },
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def get(self, request, pk):
        """Retrieve specific linked account details"""
        try:
            account = LinkedAccount.objects.get(pk=pk, user=request.user)
            return Response(
                {
                    'id': account.id,
                    'bank_name': account.bank_name,
                    'account_number': f"••••{account.account_number[-4:]}",
                    'routing_number': f"••••{account.routing_number[-4:]}",
                    'default': account.default,
                    'billing_name': account.billing_name,
                    'bank_address': {
                        'line1': account.bank_address_line1,
                        'city': account.bank_address_city,
                        'country': account.bank_address_country
                    }
                },
                status=status.HTTP_200_OK
            )
        except ObjectDoesNotExist:
            return Response(
                {'error': 'Account not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

# Notifcations
@api_view(['GET'])
def get_notifications(request):
    notifications = Notification.objects.filter(user=request.user, is_read=False)
    serializer = NotificationSerializer(notifications, many=True)
    return Response({"notifications": serializer.data})


# Points System
class UserPointsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    """ User Points API """

    def list(self, request):
        user_points = get_object_or_404(UserPoints, user=request.user)
        serializer = UserPointsSerializer(user_points)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def transactions(self, request):
        transactions = PointTransaction.objects.filter(user=request.user).order_by('-created_at')
        serializer = PointTransactionSerializer(transactions, many=True)
        return Response(serializer.data)

class RedeemPointsViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    """ Redeem Points API """

    @action(detail=True, methods=['post'])
    def redeem(self, request, pk=None):
        reward = get_object_or_404(Reward, pk=pk)
        user_points = get_object_or_404(UserPoints, user=request.user)

        if user_points.deduct_points(reward.points_required, f"Redeemed {reward.name}"):
            PointTransaction.objects.create(
                user=request.user,
                points=-reward.points_required,
                description=f"Redeemed {reward.name}"
            )
            return Response({
                "message": f"Successfully redeemed {reward.name}",
                "remaining_points": user_points.balance  # Add this line
            }, status=status.HTTP_200_OK)
        return Response({"error": "Not enough points"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_referral_code(request):
    """
    Returns the authenticated user's referral code.
    Example response: 
    {
        "referral_code": "ALI7421",
        "share_message": "Join using my code ALI7421 for rewards!"
    }
    """
    user = request.user  # Gets the logged-in user
    
    if not user.referral_code:
        return Response(
            {"error": "Referral code not generated. Please contact support."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    return Response({
        "referral_code": user.referral_code,
        "share_message": f"Join using my code {user.referral_code} for rewards!"
    })
    
    
class RewardViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Reward.objects.all()
    serializer_class = RewardSerializer
    