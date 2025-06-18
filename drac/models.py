from django.db import models
from django.contrib.auth import get_user_model
from app.models import Transaction, UserProfile  
from kyc.models import KYCRequest 

User = get_user_model()

class Anomaly(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)
    description = models.TextField()
    detected_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, default="Pending")
    
    def __str__(self):
        return f"Anomaly {self.id} - {self.status}"

class ComplianceCheck(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    kyc = models.ForeignKey(KYCRequest, on_delete=models.CASCADE)
    result = models.TextField()
    checked_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Compliance Check for {self.user}"


class AuditLog(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE)
    description = models.TextField()
    audited_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=50, default="Completed")
    
    def __str__(self):
        return f"Audit {self.id} - {self.status}"

class Reconciliation(models.Model):
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, null=True, blank=True)
    expected_amount = models.DecimalField(max_digits=12, decimal_places=2)
    actual_amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=50, default="Pending")
    discrepancy_details = models.TextField(null=True, blank=True) 
    reconciled_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Reconciliation {self.id} - {self.status}"
