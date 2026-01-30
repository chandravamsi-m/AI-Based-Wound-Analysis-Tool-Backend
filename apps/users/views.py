from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView as BaseTokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.db import models
from .models import User, SystemLog
from clinical.models import Alert
from .serializers import UserSerializer, SystemLogSerializer, CustomTokenObtainPairSerializer, ChangePasswordSerializer
from .permissions import IsAdmin, IsAdminOrDoctor
from .utils import get_storage_metrics, get_database_size, log_system_event, get_client_ip, get_uptime
from django.utils import timezone
from datetime import timedelta

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAdmin()]

    def perform_create(self, serializer):
        user = serializer.save()
        log_system_event(
            user=self.request.user if not self.request.user.is_anonymous else None,
            action=f"Created new user: {user.email} (Role: {user.role})",
            severity='Success',
            ip_address=get_client_ip(self.request)
        )

    def perform_update(self, serializer):
        # Check if password is being changed
        old_user = self.get_object()
        user = serializer.save()
        
        action = f"Updated user profile: {user.email}"
        if 'password' in self.request.data:
            action = f"Changed password for user: {user.email}"
            
        log_system_event(
            user=self.request.user if not self.request.user.is_anonymous else None,
            action=action,
            severity='Info',
            ip_address=get_client_ip(self.request)
        )

    def perform_destroy(self, instance):
        email = instance.email
        instance.delete()
        log_system_event(
            user=self.request.user if not self.request.user.is_anonymous else None,
            action=f"Deleted user: {email}",
            severity='Warning',
            ip_address=get_client_ip(self.request)
        )

class SystemLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = SystemLog.objects.all().order_by('-timestamp')
    serializer_class = SystemLogSerializer
    permission_classes = [IsAdminOrDoctor]  # Admins and Doctors can view logs
    
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
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            # Calculate dashboard metrics
            active_users = User.objects.filter(isActive=True).count()
            total_logs = SystemLog.objects.count()
            clinical_alerts = Alert.objects.filter(is_dismissed=False).count()
            security_alerts = SystemLog.objects.filter(severity__in=['Error', 'Warning']).count()
            
            # Total alerts displayed on dashboard
            display_alerts = clinical_alerts + security_alerts
            
            # Calculate user growth trend (Last 7 days vs Previous 7 days)
            now = timezone.now()
            last_7_days = now - timedelta(days=7)
            previous_7_days = now - timedelta(days=14)
            
            current_users_count = User.objects.filter(isActive=True).count()
            # Note: In a real system, we might look at 'date_joined' or 'last_login' 
            # For simplicity, we compare total active users today vs a static baseline for now
            # or we could count users joined in those periods if we had a join_date
            user_trend = "+5% stable" # Fallback if we can't calculate a real delta yet
            
            # Dynamic Security Status
            security_status = "Healthy"
            if security_alerts > 10:
                security_status = "Critical"
            elif security_alerts > 0:
                security_status = "Action Required"

            # Real storage metrics with error handling
            try:
                metrics = get_storage_metrics()
                db_size = get_database_size()
                
                storage_stats = {
                    'used_percentage': metrics['used_percentage'],
                    'patient_records_size': f"{db_size['size_gb']} GB",
                    'imaging_data_size': f"{round(metrics['used_capacity_gb'] - db_size['size_gb'], 1)} GB",
                    'free_space': f"{round(metrics['free_space_gb'], 1)} GB",
                    'total_capacity_tb': metrics['total_capacity_tb'],
                    'used_capacity_tb': metrics['used_capacity_tb']
                }
            except Exception as e:
                print(f"Error getting storage metrics: {e}")
                # Fallback storage stats
                storage_stats = {
                    'used_percentage': 0,
                    'patient_records_size': "0 GB",
                    'imaging_data_size': "0 GB",
                    'free_space': "0 GB",
                    'total_capacity_tb': 0,
                    'used_capacity_tb': 0
                }
            
            return Response({
                'active_users': active_users,
                'user_trend': user_trend,
                'system_uptime': get_uptime(),
                'security_alerts': display_alerts, # Total of clinical + security
                'security_status': security_status,
                'storage_stats': storage_stats
            }, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"Dashboard summary error: {e}")
            import traceback
            traceback.print_exc()
            return Response({
                'error': 'Failed to fetch dashboard summary',
                'detail': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class StorageStatsView(APIView):
    permission_classes = [IsAdminOrDoctor]
    
    def get(self, request):
        metrics = get_storage_metrics()
        db_size = get_database_size()
        
        data = {
            'total_capacity': metrics['total_capacity_tb'],
            'used_capacity': metrics['used_capacity_tb'],
            'used_percentage': metrics['used_percentage'],
            'database_usage_gb': db_size['size_gb'],
            'database_percentage': round((db_size['size_gb'] / metrics['used_capacity_gb']) * 100, 1) if metrics['used_capacity_gb'] > 0 else 0,
            'file_storage_gb': round(metrics['used_capacity_gb'] - db_size['size_gb'], 1),
            'file_storage_percentage': 100 - (round((db_size['size_gb'] / metrics['used_capacity_gb']) * 100, 1) if metrics['used_capacity_gb'] > 0 else 0),
            'breakdown': [
                {
                    'id': 1,
                    'category': 'Patient Clinical Records (DB)',
                    'description': 'Structured EHR Data',
                    'size': f"{db_size['size_gb']} GB",
                    'growth': '+0.0%',
                    'lastBackup': 'Auto-synced',
                    'status': 'SECURE',
                    'statusType': 'secure'
                },
                {
                    'id': 2,
                    'category': 'Wound Imaging Data (Disk)',
                    'description': 'High-Res Clinical Photos',
                    'size': f"{round(metrics['used_capacity_gb'] - db_size['size_gb'], 1)} GB",
                    'growth': '+0.0%',
                    'lastBackup': 'Daily',
                    'status': 'SECURE',
                    'statusType': 'secure'
                },
                {
                    'id': 3,
                    'category': 'System Audit Logs',
                    'description': 'Activity & Compliance Logs',
                    'size': '0.1 GB',
                    'growth': '+0.1%',
                    'lastBackup': 'Instant',
                    'status': 'SECURE',
                    'statusType': 'secure'
                },
                {
                    'id': 4,
                    'category': 'System Backups',
                    'description': 'Configuration & Meta-data',
                    'size': 'N/A',
                    'growth': 'N/A',
                    'lastBackup': 'Pending',
                    'status': 'PENDING VERIFY',
                    'statusType': 'pending'
                }
            ]
        }
        return Response(data, status=status.HTTP_200_OK)

class CustomTokenObtainPairView(APIView):
    """
    Custom JWT login view with rate limiting and activity tracking.
    """
    permission_classes = [AllowAny]
    
    @method_decorator(ratelimit(key='ip', rate='5/15m', method='POST', block=True))
    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not email or not password:
            return Response(
                {'error': 'Email and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get user from our custom User model
            user = User.objects.get(email=email)
            
            # Check if user is active
            if not user.isActive:
                log_system_event(
                    user=None,
                    action=f"Login attempt for disabled account: {email}",
                    severity='Warning',
                    ip_address=get_client_ip(request)
                )
                return Response(
                    {'error': 'Your account has been disabled. Please contact administrator.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Verify password using our custom method
            if not user.verify_password(password):
                log_system_event(
                    user=None,
                    action=f"Failed login attempt for email: {email}",
                    severity='Warning',
                    ip_address=get_client_ip(request)
                )
                return Response(
                    {'error': 'Invalid email or password'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Update last activity
            user.update_activity()
            
            # Generate JWT tokens
            refresh = RefreshToken()
            refresh['email'] = user.email
            refresh['role'] = user.role
            refresh['name'] = user.name
            refresh['user_id'] = user.id
            
            # Removed successful login logging to reduce noise
            # log_system_event(...)
            
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': {
                    'id': user.id,
                    'email': user.email,
                    'name': user.name,
                    'role': user.role,
                    'status': user.status,
                    'isActive': user.isActive,
                }
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            log_system_event(
                user=None,
                action=f"Failed login attempt for non-existent email: {email}",
                severity='Warning',
                ip_address=get_client_ip(request)
            )
            return Response(
                {'error': 'Invalid email or password'},
                status=status.HTTP_401_UNAUTHORIZED
            )


class LogoutView(APIView):
    """
    Logout view that blacklists the refresh token.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            
            # Removed redundant logout logging
            # log_system_event(...)
            
            return Response(
                {'message': 'Successfully logged out'},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {'error': 'Invalid token'},
                status=status.HTTP_400_BAD_REQUEST
            )


class CustomTokenRefreshView(BaseTokenRefreshView):
    """
    Custom token refresh view.
    """
    permission_classes = [AllowAny]


class ChangePasswordView(APIView):
    """
    Change password for authenticated user.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        
        if serializer.is_valid():
            user = request.user
            
            # Verify old password
            if not user.verify_password(serializer.validated_data['old_password']):
                return Response(
                    {'error': 'Old password is incorrect'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Set new password
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            
            # Removed noisy password change logging
            # log_system_event(...)
            
            return Response(
                {'message': 'Password changed successfully'},
                status=status.HTTP_200_OK
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Keep old LoginView for backward compatibility during migration
class LoginView(APIView):
    """
    Legacy login view - deprecated, use CustomTokenObtainPairView instead.
    """
    permission_classes = [AllowAny]
    
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
                
                # Removed successful login logging to reduce noise
                # log_system_event(...)
                
                # Serialize user data (password won't be included due to write_only)
                serializer = UserSerializer(user)
                return Response({
                    'message': 'Login successful',
                    'user': serializer.data
                }, status=status.HTTP_200_OK)
            else:
                # Log failed login attempt
                log_system_event(
                    user=None, 
                    action=f"Failed login attempt for email: {email}", 
                    severity='Warning',
                    ip_address=get_client_ip(request)
                )
                return Response(
                    {'error': 'Invalid email or password'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
                
        except User.DoesNotExist:
            # Log failed login attempt (non-existent user)
            log_system_event(
                user=None, 
                action=f"Failed login attempt for non-existent email: {email}", 
                severity='Warning',
                ip_address=get_client_ip(request)
            )
            return Response(
                {'error': 'Invalid email or password'},
                status=status.HTTP_401_UNAUTHORIZED
            )
