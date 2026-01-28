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
