from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TradingViewSet

# Create a router and register the TradingViewSet
router = DefaultRouter()
router.register(r'trading', TradingViewSet, basename='trading')

urlpatterns = [
    path('', include(router.urls)),  # Registering the router URLs
]
