from django.db import models

class Patient(models.Model):
    name = models.CharField(max_length=100)
    mrn = models.CharField(max_length=50, unique=True, verbose_name="Medical Record Number")
    
    def __str__(self):
        return f"{self.name} ({self.mrn})"

class Alert(models.Model):
    PRIORITY_CHOICES = [
        ('Critical', 'Critical'),
        ('Warning', 'Warning'),
        ('Info', 'Info'),
    ]
    
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=100) # e.g., 'Deteriorating Wound'
    description = models.TextField(blank=True)
    severity = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='Info')
    timestamp = models.DateTimeField(auto_now_add=True)
    is_dismissed = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.severity}: {self.alert_type} - {self.patient.name}"
