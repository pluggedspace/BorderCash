from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest
from .models import Anomaly, ComplianceCheck, AuditLog, Reconciliation
from .tasks import detect_anomaly_task, run_compliance_check_task, run_audit_task, scheduled_reconciliation_task
from app.models import Transaction, User
from kyc.models import KYCRequest


# Anomaly Detection View
def detect_anomaly_view(request, transaction_id):
    if request.method != 'POST':
        return HttpResponseBadRequest("Invalid request method. Use POST.")
    
    try:
        transaction = get_object_or_404(Transaction, id=transaction_id)
        detect_anomaly_task.delay(transaction.id)
        return JsonResponse({"message": f"Anomaly detection started successfully for transaction {transaction.id}."})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# Compliance Check View
def run_compliance_check_view(request, user_id):
    if request.method != 'POST':
        return HttpResponseBadRequest("Invalid request method. Use POST.")
    
    try:
        user = get_object_or_404(User, id=user_id)
        run_compliance_check_task.delay(user.id)
        return JsonResponse({"message": f"Compliance check initiated for user {user.username}."})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# Audit View
def run_audit_view(request, transaction_id):
    if request.method != 'POST':
        return HttpResponseBadRequest("Invalid request method. Use POST.")
    
    try:
        transaction = get_object_or_404(Transaction, id=transaction_id)
        run_audit_task.delay(transaction.id)
        return JsonResponse({"message": f"Audit process initiated successfully for transaction {transaction.id}."})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# Scheduled Reconciliation View
def scheduled_reconciliation_view(request):
    if request.method != 'POST':
        return HttpResponseBadRequest("Invalid request method. Use POST.")
    
    try:
        scheduled_reconciliation_task.delay()
        return JsonResponse({"message": "Scheduled reconciliation process initiated."})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500})
