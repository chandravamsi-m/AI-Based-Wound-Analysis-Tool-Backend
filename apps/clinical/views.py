from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count, Avg
from django.utils import timezone
from .models import Patient, Alert, Wound, WoundAssessment, Task, ClinicalRecord
from .serializers import (
    PatientSerializer, AlertSerializer, WoundAssessmentSerializer, 
    WoundSerializer, TaskSerializer, ClinicalRecordSerializer
)
import random
import base64
import io
from PIL import Image

# --- Shared Viewsets ---

class PatientViewSet(viewsets.ModelViewSet):
    """
    Combined Patient Management.
    """
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Patient.objects.none()
            
        # If 'all' is requested, show everything (e.g. for search/intake)
        if self.request.query_params.get('all') == 'true':
            # Security Audit: Log if a Nurse accesses the full registry (Break-the-Glass)
            if hasattr(user, 'role') and user.role == 'Nurse':
                from users.utils import log_system_event, get_client_ip
                log_system_event(
                    user=user,
                    action="Accessed Global Patient Registry (Break-the-Glass Protocol)",
                    severity='Warning',
                    ip_address=get_client_ip(self.request)
                )
            return Patient.objects.all().order_by('name')

        # Nurses see patients assigned to them via tasks by default
        if user.role == 'Nurse':
            return Patient.objects.filter(tasks__assigned_to=user).distinct()
        
        # Doctors and Admins see all
        return Patient.objects.all()

    def perform_create(self, serializer):
        # Save the patient record
        patient = serializer.save()
        
        # Clinical Workflow: If a Nurse adds a patient, 
        # automatically assign an initial assessment task to them
        # This ensures the patient shows up in their restricted 'My Patients' list
        user = self.request.user
        if hasattr(user, 'role') and user.role == 'Nurse':
            # Format time as HH:MM string to match model's CharField requirements
            future_time = timezone.now() + timezone.timedelta(hours=2)
            time_str = future_time.strftime("%H:%M")
            
            Task.objects.create(
                patient=patient,
                assigned_to=user,
                title="Initial Wound Assessment",
                description=f"Auto-generated task for new patient intake: {patient.name}",
                priority='Medium',
                due_time=time_str
            )

class AlertViewSet(viewsets.ModelViewSet):
    queryset = Alert.objects.filter(is_dismissed=False).order_by('-timestamp')
    serializer_class = AlertSerializer

    @action(detail=True, methods=['post'])
    def dismiss(self, request, pk=None):
        alert = self.get_object()
        alert.is_dismissed = True
        alert.save()
        return Response({'status': 'alert dismissed'}, status=status.HTTP_200_OK)

# --- Doctor Specific Views ---

class DoctorDashboardSummaryView(APIView):
    def get(self, request):
        active_count = Patient.objects.filter(tasks__isnull=False).distinct().count() or 3
        critical_cases = Alert.objects.filter(severity='Critical', is_dismissed=False).count() or 1
        
        return Response({
            'active_patients': active_count,
            'active_patients_trend': '+12%',
            'critical_cases': critical_cases,
            'critical_cases_trend': '-2',
            'healing_rate': '84%',
            'healing_rate_trend': '+5%',
            'avg_assessment_time': '4.2m',
            'avg_assessment_time_trend': '-30s',
            'greeting': f'Good Morning, Dr. {request.user.name.split()[-1]}',
            'status_message': f'You have {active_count} active patients and {critical_cases} pending alerts today.'
        })

class DoctorDashboardStatsView(APIView):
    def get(self, request):
        today = timezone.now().date()
        active_patients = Patient.objects.filter(tasks__isnull=False).distinct().count()
        pending_tasks = Task.objects.filter(status='PENDING').count()
        completed_today = Task.objects.filter(status='COMPLETED', completed_at__date=today).count()
        scans = WoundAssessment.objects.filter(created_at__date=today).count()

        return Response({
            'active_patients': active_patients,
            'pending_tasks': pending_tasks,
            'completed_today': completed_today,
            'scans': scans,
            'active_patients_trend': '+12%',
            'healing_rate': '84%',
            'greeting': f'Good Morning, {request.user.name}'
        })

class DoctorScheduledTasksView(APIView):
    def get(self, request):
        # Fetch pending tasks for doctor's ward
        tasks = Task.objects.filter(status='PENDING').order_by('due_time')[:5]
        
        if not tasks.exists():
            return Response([
                {
                    'id': 1,
                    'time': '09:30',
                    'title': 'Assessment: James Wilson',
                    'description': 'Follow-up on Left Heel ulcer • Room 302',
                },
                {
                    'id': 2,
                    'time': '10:45',
                    'title': 'Review: Sarah Parker',
                    'description': 'Post-op dressing change • Room 115',
                }
            ])
            
        return Response([
            {
                'id': t.id,
                'time': t.due_time,
                'title': t.title,
                'description': f'Patient: {t.patient.name} • Bed {t.patient.bed or "N/A"}'
            } for t in tasks
        ])

class WoundStatsView(APIView):
    def get(self, request):
        # Keep mock metrics for visual charts
        return Response({
            'distribution': [
                {'category': 'Venous Ulcers', 'percentage': 45},
                {'category': 'Pressure Ulcers', 'percentage': 30},
                {'category': 'Diabetic Foot', 'percentage': 25}
            ],
            'healing_trend': [62, 68, 65, 78, 80, 88],
            'priority_cases': [
                {
                    'id': a.id,
                    'patient_name': a.patient.name,
                    'risk_level': 'HIGH RISK' if a.severity == 'Critical' else 'MODERATE',
                    'description': a.description or "High Severity Detected: Immediate review recommended."
                } for a in Alert.objects.filter(is_resolved=False)[:3]
            ]
        })

class DoctorTaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    queryset = Task.objects.all()

class AlertStatsView(APIView):
    def get(self, request):
        total_active = Alert.objects.filter(is_dismissed=False).count()
        return Response({
            'total_active': total_active,
            'avg_response_time': '42m',
            'critical_resolved': Alert.objects.filter(severity='Critical', is_resolved=True).count(),
            'trend': '8% from yesterday'
        })

# --- Nurse Specific Views ---

class NurseDashboardStatsView(APIView):
    def get(self, request):
        user = request.user
        today = timezone.now().date()
        
        active_patients = Patient.objects.filter(tasks__assigned_to=user).distinct().count()
        doc_due = Task.objects.filter(assigned_to=user, status='PENDING').count()
        completed = Task.objects.filter(assigned_to=user, status='COMPLETED').count()
        scans = WoundAssessment.objects.filter(created_at__date=today).count()

        return Response({
            'active_patients': active_patients,
            'doc_due': doc_due,
            'completed': completed,
            'scans': scans
        })

class NurseTaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer

    def get_queryset(self):
        return Task.objects.filter(assigned_to=self.request.user)

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.status == 'COMPLETED' and not instance.completed_at:
             instance.completed_at = timezone.now()
             instance.is_completed = True
             instance.save()

class NurseClinicalViewSet(viewsets.ViewSet):
    @action(detail=False, methods=['post'], url_path='upload-wound')
    def upload_wound(self, request):
        user = request.user
        patient_pk = request.data.get('patient')
        image = request.FILES.get('image')
        notes = request.data.get('notes', '')
        
        try:
            patient = Patient.objects.get(id=patient_pk)
            wound, _ = Wound.objects.get_or_create(patient=patient)
        except Patient.DoesNotExist:
            return Response({"error": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)

        # Advanced Image Processing Pipeline
        try:
            # 1. Open and Verify Image
            img = Image.open(image)
            
            # 2. Clinical Compression & Resizing
            # Maintains clinical detail while reducing DB bloat
            max_size = (1200, 1200)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # 3. Handle Color Profiles (Convert PNG/RGBA to JPEG friendly RGB)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # 4. Binary to Base64 Conversion
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=70, optimize=True)
            encoded_string = base64.b64encode(buffer.getvalue()).decode('utf-8')
            base64_image_uri = f"data:image/jpeg;base64,{encoded_string}"
            
        except Exception as e:
            return Response({"error": f"Image processing failed: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        # Mock AI Analysis (Placeholder for Actual ML Model)
        width = round(random.uniform(2.0, 10.0), 1)
        depth = round(random.uniform(0.5, 3.0), 1)
        stage = random.choice(['Stage 1', 'Stage 2', 'Stage 3'])
        
        assessment = WoundAssessment.objects.create(
            nurse=user,
            wound=wound,
            image=base64_image_uri, # Store the compressed string directly
            notes=notes,
            width=width,
            depth=depth,
            stage=stage
        )
        
        if stage == 'Stage 3' or stage == 'Unstageable':
            assessment.is_escalated = True
            assessment.save()
            Alert.objects.create(
                patient=patient,
                assessment=assessment,
                triggered_by=user,
                alert_type="High Severity Detected",
                description=f"AI classified as {stage}",
                severity="Critical"
            )

        return Response(WoundAssessmentSerializer(assessment).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='record-vitals')
    def record_vitals(self, request):
        serializer = ClinicalRecordSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(recorded_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
