from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from django.db import transaction
from .models import KYCRequest
from .services.dropbox import DropboxService
from .tasks import process_kyc_task
import logging




logger = logging.getLogger(__name__)

class UploadKycDocumentView(APIView):
    """
    Handles document uploads and auto-submits the KYC request.
    Returns a response immediately so the frontend can close the upload modal.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_profile = request.user.userprofile
        dropbox_service = DropboxService.get_instance()

        required_files = ["id_document", "selfie", "address_document"]
        uploaded_files = {}

        # Check for missing files
        for file_type in required_files:
            file = request.FILES.get(file_type)
            if not file:
                return Response({"error": f"Missing {file_type}"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                # Upload to Dropbox and get file URL
                file_path = f"/kyc/{user_profile.user.id}/{file.name}"
                file_url = dropbox_service.upload_file(file_path, file, file.name)
                if not file_url:
                    return Response({"error": f"Failed to upload {file_type}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                uploaded_files[file_type] = file_url
            except Exception as e:
                logger.error(f"Failed to upload {file_type}: {str(e)}")
                return Response({"error": f"Failed to upload {file_type}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Ensure no duplicate pending requests
        if KYCRequest.objects.filter(user=user_profile, status="pending").exists():
            return Response({"error": "You already have a pending KYC request."}, status=status.HTTP_400_BAD_REQUEST)

        # Auto-create and submit KYCRequest with user details
        try:
            with transaction.atomic():
                kyc_request = KYCRequest.create_from_profile(
                    user_profile,
                    id_document=uploaded_files["id_document"],
                    selfie=uploaded_files["selfie"],
                    address_document=uploaded_files["address_document"],
                    status="pending"
                )

                # Schedule background KYC processing (Celery)
                process_kyc_task.apply_async(args=[kyc_request.id], countdown=300)

            return Response({
                "message": "Documents uploaded successfully. Verification is in progress.",
                "kyc_status": "pending",
                "kyc_id": kyc_request.id  # Return the KYC request ID
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Failed to create KYC request: {str(e)}")
            return Response({"error": "Error processing KYC request"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def kyc_status(request):
    """
    API to allow frontend to poll for KYC status.
    """
    user_profile = request.user.userprofile
    latest_request = KYCRequest.objects.filter(user=user_profile).order_by('-created_at').first()

    return Response({
        "status": user_profile.kyc_status,
        "is_completed": user_profile.is_kyc_completed,
        "last_verification_date": latest_request.reviewed_at if latest_request else None,
        "pending_verification": latest_request.status == "pending" if latest_request else False
    })
