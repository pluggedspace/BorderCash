from django.urls import path
from .views import UploadKycDocumentView, kyc_status

urlpatterns = [
    path('upload/', UploadKycDocumentView.as_view(), name='upload-kyc-document'),
    path('status/', kyc_status, name='kyc-status'),
]
