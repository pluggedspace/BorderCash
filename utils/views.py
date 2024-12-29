import logging
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from app.models import Transaction, User
from .serializers import ProductSerializer, OrderSerializer
from .services import UtilityService, AirtimeService, GiftCardService, ReloadlyBaseService

logger = logging.getLogger(__name__)


class AirtimeTopUpView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def post(request):
        data = request.data
        phone = data.get("phone_number")
        operator_id = data.get("operator_id")
        amount = data.get("amount")
        try:
            result = AirtimeService.top_up(request.user, phone, operator_id, amount)
            return Response(result, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": "Failed to complete the transaction"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UtilityPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    @staticmethod
    def get(request):
        try:
            # Fetch available billers
            billers = UtilityService.fetch_billers()

            if not billers:
                return Response(
                    {"error": "No available billers found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Prepare the response data
            return Response({"billers": billers}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @staticmethod
    def post(request):
        data = request.data
        account_number = data.get("account_number")
        provider_id = data.get("provider_id")
        amount = data.get("amount")

        # Input validation
        if not account_number or not provider_id or not amount:
            return Response(
                {"error": "Missing required fields: account_number, provider_id, amount"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Convert amount to float to ensure it is treated as a numerical value
            amount = float(amount)

            # Call the utility payment service
            result = UtilityService.pay_bill(request.user, account_number, provider_id, amount)

            # Save transaction details
            Transaction.objects.create(
                user=request.user,
                transaction_type="utility",
                amount=amount,
                details=result,
            )

            return Response(result, status=status.HTTP_200_OK)

        except ValueError as e:
            # Handle value conversion errors (e.g., non-numeric amounts)
            return Response(
                {"error": f"Invalid input: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except RuntimeError as e:
            # Handle service-specific errors (e.g., API failures)
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:
            # Catch any unexpected errors
            return Response(
                {"error": "An unexpected error occurred. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GiftCardPurchaseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        gift_card_id = data.get("gift_card_id")
        amount = data.get("amount")
        commission = data.get("commission", 0.00)  # Optional commission value

        try:
            result = GiftCardService.purchase_gift_card(
                request.user, gift_card_id, amount, commission
            )
            return Response(result, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": "Failed to complete the transaction"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GiftCardListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            endpoint = "/giftcards"
            gift_cards = ReloadlyBaseService.make_request(endpoint)
            return Response(gift_cards, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": "Failed to fetch gift cards"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class GiftCardDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, gift_card_id):
        try:
            endpoint = f"/giftcards/{gift_card_id}"
            gift_card_details = ReloadlyBaseService.make_request(endpoint)
            return Response(gift_card_details, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": "Failed to fetch gift card details"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# Shop
class ProductCreateView(APIView):
    @staticmethod
    def post(request):
        serializer = ProductSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OrderCreateView(APIView):
    @staticmethod
    def post(request):
        user_id = request.data.get("user")
        total_cost = request.data.get("total_cost")
        user = get_object_or_404(User, id=user_id)

        if user.swif_balance < float(total_cost):
            return Response({"error": "Insufficient balance"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = OrderSerializer(data=request.data)
        if serializer.is_valid():
            # Deduct balance and save the order
            user.swif_balance -= float(total_cost)
            user.save()
            serializer.save(payment_status="Completed")
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
