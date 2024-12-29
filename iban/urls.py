from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import IBANAccountViewSet, CardViewSet, TransactionViewSet, NotificationViewSet

router = DefaultRouter()
router.register(r'ibans', IBANAccountViewSet, basename='iban')
router.register(r'cards', CardViewSet, basename='card')
router.register(r'transactions', TransactionViewSet, basename='transaction')
router.register(r'notifications', NotificationViewSet, basename='notification')

urlpatterns = [
    path('', include(router.urls)),
]
