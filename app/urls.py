from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenObtainPairView
from rest_framework.routers import DefaultRouter
from . import views
from .views import (
    password_reset_request, password_reset_confirm, account_view, balance_view,
    transaction_view, health_check, LoginView, logout_view, withdrawal_webhook,
    LinkedAccountView, get_notifications, EditUserProfileView,
    UserProfileAndAccountView, set_transaction_pin, UserPointsViewSet, RedeemPointsViewSet, verify_email, get_referral_code, RewardViewSet
)

router = DefaultRouter()
router.register(r'rewards', RewardViewSet, basename='reward')

urlpatterns = [
    path('register/', views.register_user, name='register_user'),
    path('edit-profile/', EditUserProfileView.as_view(), name='edit-profile'),
    path('userprofile-and-account/', UserProfileAndAccountView.as_view(), name='user_profile_and_account'),
    path('verify-email/<str:token>/', verify_email, name='verify-email'),

    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('login/', LoginView.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),

    path('password-reset/', password_reset_request, name='password_reset_request'),
    path('password-reset-confirm/<uidb64>/<token>/', password_reset_confirm, name='password_reset_confirm'),
    path('pin/', set_transaction_pin, name='set_transaction_pin'),

    path('account/', account_view, name='account_view'),
    path('balance/', balance_view, name='balance_view'),
    path('transactions/', transaction_view, name='transaction_view'),

    path('deposit/', views.initiate_deposit, name='deposit'),
    path('withdraw/', views.initiate_withdrawal, name='withdraw'),
    path('webhook/withdrawal/', withdrawal_webhook, name='withdrawal_webhook'),
    path('transfer/', views.initiate_transfer, name='transfer'),

    path('link-account/', LinkedAccountView.as_view(), name='linked_accounts'),
    path('linked-account/<int:pk>/', LinkedAccountView.as_view(), name='linked_account_detail'),

    path('notifications/', get_notifications, name='get_notifications'),
    path('health/', health_check, name='health_check'),

    # User Points API
    path('user-points/', UserPointsViewSet.as_view({'get': 'list'}), name='user-points'),
    path('user-points/transactions/', UserPointsViewSet.as_view({'get': 'transactions'}), name='user-points-transactions'),

    # Redeem Rewards API
    path('redeem/<int:pk>/redeem/', RedeemPointsViewSet.as_view({'post': 'redeem'}), name='redeem-points'),

    path('referral-code/', get_referral_code, name='get_referral_code'),
]

# Add router URLs (like rewards/) at the end
urlpatterns += router.urls