from rest_framework import serializers
from .models import User, SystemLog
import re

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, style={'input_type': 'password'})
    activity = serializers.SerializerMethodField()  # Computed field for dynamic activity
    

    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'password', 'status', 'role', 'activity', 'last_activity', 'isActive']
        extra_kwargs = {
            'password': {'write_only': True},
            'last_activity': {'read_only': True}
        }
    
    def get_activity(self, obj):
        """Return dynamic activity status"""
        return obj.get_activity_status()
    

    def validate_password(self, value):
        """
        Validate password requirements:
        - At least 8 characters
        - At least one uppercase letter
        - At least one number
        - At least one special character
        """
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long.")
        
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter.")
        
        if not re.search(r'[0-9]', value):
            raise serializers.ValidationError("Password must contain at least one number.")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', value):
            raise serializers.ValidationError("Password must contain at least one special character.")
        
        return value
    
    def create(self, validated_data):
        """Create user with hashed password"""
        password = validated_data.pop('password', None)
        if not password:
            raise serializers.ValidationError({"password": "Password is required when creating a user."})
        
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user
    
    def update(self, instance, validated_data):
        """Update user, hash password if provided"""
        password = validated_data.pop('password', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance

class SystemLogSerializer(serializers.ModelSerializer):
    user_name = serializers.ReadOnlyField(source='user.name', default='System')

    class Meta:
        model = SystemLog
        fields = ['id', 'timestamp', 'user', 'user_name', 'ip_address', 'action', 'severity']
