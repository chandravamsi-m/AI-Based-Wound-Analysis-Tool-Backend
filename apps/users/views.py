from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db import models
from .models import User, SystemLog
from .serializers import UserSerializer, SystemLogSerializer

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

class SystemLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SystemLog.objects.all().order_by('-timestamp')
    serializer_class = SystemLogSerializer
    
    def get_queryset(self):
        queryset = SystemLog.objects.all().order_by('-timestamp')
        
        # Search by user name, action, or IP address
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                models.Q(user__name__icontains=search) |
                models.Q(action__icontains=search) |
                models.Q(ip_address__icontains=search)
            )
        
        # Filter by severity
        severity = self.request.query_params.get('severity', None)
        if severity and severity != 'All Severities':
            queryset = queryset.filter(severity=severity)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        return queryset

class DashboardSummaryView(APIView):
    def get(self, request):
        # Calculate dashboard metrics
        active_users = User.objects.filter(isActive=True).count()
        total_logs = SystemLog.objects.count()
        security_alerts = SystemLog.objects.filter(severity__in=['Error', 'Warning']).count()
        
        # Mock storage data for now (to be replaced with real storage logic later)
        storage_stats = {
            'used_percentage': 75,
            'patient_records_size': '824 GB',
            'imaging_data_size': '1.2 TB',
            'free_space': '650 GB'
        }
        
        return Response({
            'active_users': active_users,
            'system_uptime': '99.98%',
            'security_alerts': security_alerts,
            'storage_stats': storage_stats
        }, status=status.HTTP_200_OK)

class LoginView(APIView):
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not email or not password:
            return Response(
                {'error': 'Email and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=email)
            
            # Check if user is active
            if not user.isActive:
                return Response(
                    {'error': 'Your account has been disabled. Please contact administrator.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Verify password
            if user.verify_password(password):
                # Update last activity
                user.update_activity()
                
                # Serialize user data (password won't be included due to write_only)
                serializer = UserSerializer(user)
                return Response({
                    'message': 'Login successful',
                    'user': serializer.data
                }, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'error': 'Invalid email or password'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
                
        except User.DoesNotExist:
            return Response(
                {'error': 'Invalid email or password'},
                status=status.HTTP_401_UNAUTHORIZED
            )
