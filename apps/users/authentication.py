from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import User


class CustomJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication that uses our custom User model.
    """
    def get_user(self, validated_token):
        """
        Attempts to find and return a user using the given validated token.
        """
        try:
            user_id = validated_token.get('user_id')
            user = User.objects.get(id=user_id)
            
            # Check if user is still active
            if not user.isActive:
                return None
                
            return user
        except User.DoesNotExist:
            return None
