from django.urls import path
from .views import (
    AirtimeTopUpView,
    UtilityPaymentView,
    GiftCardListView,
    GiftCardDetailView,
    GiftCardPurchaseView, ProductCreateView, OrderCreateView,
)

urlpatterns = [
    # Airtime
    path("top-up/", AirtimeTopUpView.as_view(), name="airtime-top-up"),

    # Utility Payments
    path("utilities/pay/", UtilityPaymentView.as_view(), name="utility-payment"),

    # Gift Cards
    path("giftcards/", GiftCardListView.as_view(), name="giftcard-list"),
    path("giftcards/<int:gift_card_id>/", GiftCardDetailView.as_view(), name="giftcard-detail"),
    path("giftcards/purchase/", GiftCardPurchaseView.as_view(), name="giftcard-purchase"),

    # Shop
    path('products/', ProductCreateView.as_view(), name='create-product'),
    path('orders/', OrderCreateView.as_view(), name='create-order'),
]
