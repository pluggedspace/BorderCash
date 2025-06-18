from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import monica_query_stream, test_alerts, DisputeViewSet, FAQListAPI


urlpatterns = [
    path("disputes/", DisputeViewSet.as_view({"post": "create"}), name="create_dispute"),
    path("disputes/status/", DisputeViewSet.as_view({"get": "status"}), name="dispute_status"),

    path("query/", monica_query_stream, name="monica_query_stream"),
    path("alerts/", test_alerts, name="test_alerts"),

    path("faq/", FAQListAPI.as_view(), name="faq_list"),
]
