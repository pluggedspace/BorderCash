from django.shortcuts import render
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from django_ratelimit.decorators import ratelimit
from django.http import StreamingHttpResponse
from rest_framework.decorators import action
from rest_framework.response import Response
from .utils import find_faq_answer, query_mixtral_stream, check_low_balance, check_pending_transactions, send_alert
from .notifications import send_notification 
from rest_framework.views import APIView
from rest_framework.generics import RetrieveAPIView
from .models import Dispute, FAQ
from .serializers import DisputeSerializer, FAQSerializer
from .tasks import process_refund
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from .disputes import handle_dispute, check_dispute_status


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@ratelimit(key='user', rate='5/m', method='POST', block=True)  # Limits to 5 requests per minute per user
def monica_query_stream(request):
    user = request.user
    user_query = request.data.get("query")

    if not user_query:
        return Response({"error": "Query is required"}, status=400)

    response = StreamingHttpResponse(query_mixtral_stream(user, user_query), content_type="text/plain")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"  # Disable buffering for real-time response
    return response

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def test_alerts(request):
    user = request.user  # Ensuring alerts are for the authenticated user

    low_balance_alert = check_low_balance(user)
    pending_tx_alert = check_pending_transactions(user)

    alerts = []
    if low_balance_alert:
        alerts.append(low_balance_alert)
        send_alert(user, low_balance_alert)

    if pending_tx_alert:
        alerts.append(pending_tx_alert)
        send_alert(user, pending_tx_alert)

    return Response({"alerts": alerts if alerts else "No alerts triggered"})


class FAQListAPI(APIView):
    def get(self, request):
        faq = FAQ.objects.filter(published=True)
        serializer = FAQSerializer(faq, many=True)
        return Response(serializer.data)

class DisputeViewSet(viewsets.ModelViewSet):
    """ API for handling disputes with AI categorization """
    queryset = Dispute.objects.all()
    serializer_class = DisputeSerializer
    permission_classes = [IsAuthenticated]

    
    def create(self, request, *args, **kwargs):
        """ Override create to handle AI categorization and processing """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        user_input = serializer.validated_data.get("description")
        transaction_id = serializer.validated_data.get("transaction_id")

        if not transaction_id:
            return Response({"error": "Transaction ID is required for disputes."}, status=status.HTTP_400_BAD_REQUEST)
        
        # AI dispute handling (creates dispute & processes refund if necessary)
        response_message = handle_dispute(user, user_input, transaction_id)
        
        # Return appropriate response
        return Response({"message": response_message}, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=["get"])
    def status(self, request):
        """ Allow users to check their dispute status via API """
        user = request.user
        return Response({"message": check_dispute_status(user)})