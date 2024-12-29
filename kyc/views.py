import logging
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import KYCRequest
from .serializers import KYCRequestSerializer
from .services.services import process_kyc

logger = logging.getLogger(__name__)


class KYCViewSet(viewsets.ModelViewSet):
    serializer_class = KYCRequestSerializer

    def get_queryset(self):
        """Retrieve KYC requests for the authenticated user."""
        return KYCRequest.objects.filter(user=self.request.user.userprofile)

    @action(detail=False, methods=['get'])
    def current_status(self, request):
        """Get the current KYC status of the user."""
        profile = request.user.userprofile
        return Response({
            'status': profile.kyc_status,
            'is_completed': profile.is_kyc_completed
        })

    @action(detail=False, methods=['post'])
    def submit_verification(self, request):
        """
        Submit a KYC verification request.
        """
        # Check for existing pending requests
        if KYCRequest.objects.filter(user=request.user.userprofile, status='pending').exists():
            return Response(
                {'error': 'You already have a pending KYC request'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Begin transaction to ensure atomic save and processing
        with transaction.atomic():
            kyc_request = serializer.save(user=request.user.userprofile)
            verification_result = process_kyc(kyc_request)

            # Update user profile with KYC status
            user_profile = request.user.userprofile
            user_profile.kyc_status = verification_result
            user_profile.is_kyc_completed = verification_result == 'approved'
            user_profile.save()

        return Response({
            'message': 'KYC request submitted and processed successfully',
            'kyc_status': verification_result,
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)
