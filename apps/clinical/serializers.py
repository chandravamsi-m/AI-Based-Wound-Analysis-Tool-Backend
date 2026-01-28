from rest_framework import serializers
from .models import Patient, Alert

class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = '__all__'

class AlertSerializer(serializers.ModelSerializer):
    patient_name = serializers.ReadOnlyField(source='patient.name')
    patient_mrn = serializers.ReadOnlyField(source='patient.mrn')
    
    class Meta:
        model = Alert
        fields = ['id', 'patient', 'patient_name', 'patient_mrn', 'alert_type', 'description', 'severity', 'timestamp', 'is_dismissed']
