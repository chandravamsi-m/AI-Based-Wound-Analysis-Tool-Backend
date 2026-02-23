from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta
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
        user = request.user
        # Get patients specifically assigned to this doctor
        patients = Patient.objects.filter(assigned_physician=user)
        active_count = patients.count()
        
        # Actual alert count for doctor's patients
        critical_cases = Alert.objects.filter(
            patient__assigned_physician=user,
            severity='Critical', 
            is_dismissed=False
        ).count()
        
        # Calculate a mock healing rate trend based on real assessments if they exist
        # Dynamic Healing Rate Calculation
        total_improvement = 0
        wounds_with_data = 0
        for p in patients:
            for w in p.wounds.all():
                assessments = w.assessments.order_by('created_at')
                if assessments.count() >= 2:
                    first = assessments.first()
                    last = assessments.last()
                    first_area = first.width * first.depth
                    last_area = last.width * last.depth
                    if first_area > 0:
                        improvement = ((first_area - last_area) / first_area) * 100
                        total_improvement += improvement
                        wounds_with_data += 1
        
        healing_rate_val = round(total_improvement / wounds_with_data) if wounds_with_data > 0 else 0
        healing_rate = f"{healing_rate_val}%" if wounds_with_data > 0 else "N/A"

        return Response({
            'active_patients': active_count,
            'active_patients_trend': '+5%' if active_count > 0 else '0%',
            'critical_cases': critical_cases,
            'critical_cases_trend': 'Stable',
            'healing_rate': healing_rate,
            'healing_rate_trend': '+2%',
            'avg_assessment_time': '4.2m',
            'avg_assessment_time_trend': '-10s',
            'greeting': f'Good Morning, Dr. {user.name.split()[-1]}',
            'status_message': f'You have {active_count} active patients and {critical_cases} critical notifications.',
            'my_patients': [
                {
                    'id': p.id,
                    'name': p.name,
                    'mrn': p.mrn,
                    'ward': p.ward,
                    'bed': p.bed,
                    'status': p.status or 'Stable'
                } for p in patients.order_by('-id')[:10]
            ]
        })

class DoctorDashboardStatsView(APIView):
    def get(self, request):
        user = request.user
        today = timezone.now().date()
        
        active_patients = Patient.objects.filter(assigned_physician=user).count()
        pending_tasks = Task.objects.filter(patient__assigned_physician=user, status='PENDING').count()
        completed_today = Task.objects.filter(patient__assigned_physician=user, status='COMPLETED', completed_at__date=today).count()
        scans = WoundAssessment.objects.filter(wound__patient__assigned_physician=user, created_at__date=today).count()

        return Response({
            'active_patients': active_patients,
            'pending_tasks': pending_tasks,
            'completed_today': completed_today,
            'scans': scans,
            'active_patients_trend': '+12%',
            'healing_rate': '84%',
            'greeting': f'Good Morning, Dr. {user.name}'
        })

class DoctorScheduledTasksView(APIView):
    def get(self, request):
        # Fetch pending tasks for doctor's specific patients
        tasks = Task.objects.filter(
            patient__assigned_physician=request.user, 
            status='PENDING'
        ).order_by('due_time')[:5]
        
        # If no real tasks, return empty but let the UI handle the "No Tasks" state
        # instead of showing fake data
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
        user = request.user
        
        # 1. Wound Distribution Calculation
        total_wounds = Wound.objects.filter(patient__assigned_physician=user).count()
        distribution = []
        if total_wounds > 0:
            types = Wound.objects.filter(patient__assigned_physician=user).values('wound_type').annotate(count=Count('id'))
            for t in types:
                pct = round((t['count'] / total_wounds) * 100)
                distribution.append({'category': t['wound_type'], 'percentage': pct})
        else:
            # Fallback mock for empty state UI visual
            distribution = [
                {'category': 'Venous Ulcers', 'percentage': 0},
                {'category': 'Pressure Ulcers', 'percentage': 0},
                {'category': 'Other', 'percentage': 0}
            ]

        # 2. Healing Trend (Dynamic 6-week calculation)
        healing_trend = []
        for i in range(5, -1, -1):
            start_date = timezone.now() - timedelta(weeks=i+1)
            end_date = timezone.now() - timedelta(weeks=i)
            avg_stage = WoundAssessment.objects.filter(
                wound__patient__assigned_physician=user,
                created_at__range=(start_date, end_date)
            ).aggregate(Avg('width'))['width__avg'] or 0
            # Normalize to a 0-100 score for the chart
            score = min(round(avg_stage * 10), 100) if avg_stage else random.randint(60, 90) # Fallback to random for visual if new
            healing_trend.append(score)

        # 3. Priority Cases - Actual live alerts
        priority_cases = []
        alerts = Alert.objects.filter(
            patient__assigned_physician=user,
            is_resolved=False
        ).order_by('-timestamp')[:3]

        for a in alerts:
            priority_cases.append({
                'id': a.id,
                'patient_name': a.patient.name,
                'risk_level': 'HIGH RISK' if a.severity == 'Critical' else 'MODERATE',
                'description': a.description or f"New {a.alert_type} alert triggered."
            })

        return Response({
            'distribution': distribution,
            'healing_trend': healing_trend,
            'priority_cases': priority_cases
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
        
        if stage in ['Stage 3', 'Stage 4', 'Unstageable']:
            assessment.is_escalated = True
            assessment.save()
            Alert.objects.create(
                patient=patient,
                assessment=assessment,
                triggered_by=user,
                alert_type="Critical Severity",
                description=f"AI classified as {stage}. Immediate physician review required.",
                severity="Critical"
            )
        elif stage == 'Stage 2':
            Alert.objects.create(
                patient=patient,
                assessment=assessment,
                triggered_by=user,
                alert_type="Wound Progression Warning",
                description=f"AI classified as {stage}. Monitoring frequency increase recommended.",
                severity="Warning"
            )

        return Response(WoundAssessmentSerializer(assessment).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='record-vitals')
    def record_vitals(self, request):
        serializer = ClinicalRecordSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(recorded_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
