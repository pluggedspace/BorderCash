from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenObtainPairView

from . import views
from .views import password_reset_request, password_reset_confirm, account_view, balance_view, \
    transaction_view, health_check, LoginView, logout_view, withdrawal_webhook, LinkedAccountView

urlpatterns = [
    path('register/', views.register_user, name='register_user'),

    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    path('login/', LoginView.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),

    path('password-reset/', password_reset_request, name='password_reset_request'),
    path('password-reset-confirm/<uidb64>/<token>/', password_reset_confirm, name='password_reset_confirm'),


    path('account/', account_view, name='account_view'),
    path('balance/', balance_view, name='balance_view'),
    path('transactions/', transaction_view, name='transaction_view'),

    path('deposit/', views.initiate_deposit, name='deposit'),
    path('withdraw/', views.initiate_withdrawal, name='withdraw'),
    path('webhook/withdrawal/', withdrawal_webhook, name='withdrawal_webhook'),
    path('transfer/', views.initiate_transfer, name='transfer'),

    path('health/', health_check, name='health_check'),

    path('linked-accounts/', LinkedAccountView.as_view()),  # For POST requests (linking account)
    path('linked-accounts/<int:pk>/', LinkedAccountView.as_view()),  # For GET requests (fetching Circle ID)


]
