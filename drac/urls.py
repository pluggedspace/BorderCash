from django.urls import path
from . import views

urlpatterns = [
    path('detect-anomaly/<int:transaction_id>/', views.detect_anomaly_view, name='detect_anomaly'),
    path('compliance-check/<int:user_id>/', views.run_compliance_check_view, name='compliance_check'),
    path('audit/<int:transaction_id>/', views.run_audit_view, name='audit'),
    path('scheduled-reconciliation/', views.scheduled_reconciliation_view, name='scheduled_reconciliation'),
]
