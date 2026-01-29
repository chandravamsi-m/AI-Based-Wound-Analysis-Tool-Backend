from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count, Avg
from .models import Patient, Alert
from .serializers import PatientSerializer, AlertSerializer

class AlertViewSet(viewsets.ModelViewSet):
    queryset = Alert.objects.filter(is_dismissed=False).order_by('-timestamp')
    serializer_class = AlertSerializer

    @action(detail=True, methods=['post'])
    def dismiss(self, request, pk=None):
        alert = self.get_object()
        alert.is_dismissed = True
        alert.save()
        return Response({'status': 'alert dismissed'}, status=status.HTTP_200_OK)

class AlertStatsView(APIView):
    def get(self, request):
        total_active = Alert.objects.filter(is_dismissed=False).count()
        critical_resolved_24h = Alert.objects.filter(
            severity='Critical', 
            is_dismissed=True
        ).count() # Simplified logic
        
        return Response({
            'total_active': total_active,
            'avg_response_time': '42m', # Placeholder
            'critical_resolved': critical_resolved_24h,
            'trend': '8% from yesterday'
        })

class DoctorDashboardSummaryView(APIView):
    def get(self, request):
        # Mock data for Doctor Dashboard metrics
        return Response({
            'active_patients': 3,
            'active_patients_trend': '+12%',
            'critical_cases': 1,
            'critical_cases_trend': '-2',
            'healing_rate': '84%',
            'healing_rate_trend': '+5%',
            'avg_assessment_time': '4.2m',
            'avg_assessment_time_trend': '-30s',
            'greeting': 'Good Morning, Dr. Bennett',
            'status_message': 'You have 5 scheduled assessments and 3 pending reviews today.'
        })

class DoctorScheduledTasksView(APIView):
    def get(self, request):
        # Mock data for scheduled assessments
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
            },
            {
                'id': 3,
                'time': '11:15',
                'title': 'Assessment: Robert Miller',
                'description': 'Diabetic Foot Check • Outpatient Clinic',
            }
        ])

class WoundStatsView(APIView):
    def get(self, request):
        # Mock data for charts and distribution
        return Response({
            'distribution': [
                {'category': 'Venous Ulcers', 'percentage': 45},
                {'category': 'Pressure Ulcers', 'percentage': 30},
                {'category': 'Diabetic Foot', 'percentage': 25}
            ],
            'healing_trend': [62, 68, 65, 78, 80, 88],
            'priority_cases': [
                {
                    'id': 1,
                    'patient_name': 'James Wilson',
                    'risk_level': 'HIGH RISK',
                    'description': 'Latest AI scan indicates 15% increase in necrotic tissue. Immediate review recommended.'
                }
            ]
        })
