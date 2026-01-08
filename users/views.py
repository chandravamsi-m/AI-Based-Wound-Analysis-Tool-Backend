from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import User
from .serializers import UserSerializer

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer

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
