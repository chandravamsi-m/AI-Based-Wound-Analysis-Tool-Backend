from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
from datetime import timedelta

class User(models.Model):
    STAFF_ROLES = [
        ('Doctor', 'Doctor'),
        ('Nurse', 'Nurse'),
        ('Admin', 'Admin'),
    ]
    
    STAFF_STATUS = [
        ('ACTIVE', 'ACTIVE'),
        ('DISABLED', 'DISABLED'),
    ]

    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128, blank=True, null=True)  # Stores hashed password
    status = models.CharField(max_length=20, choices=STAFF_STATUS, default='ACTIVE')
    role = models.CharField(max_length=20, choices=STAFF_ROLES)
    activity = models.CharField(max_length=50, blank=True)  # Deprecated - kept for backward compatibility
    last_activity = models.DateTimeField(null=True, blank=True)  # New field for tracking actual activity
    isActive = models.BooleanField(default=True)

    def set_password(self, raw_password):
        """Hash and set the password"""
        self.password = make_password(raw_password)

    def verify_password(self, raw_password):
        """Check if the provided password matches the hashed password"""
        return check_password(raw_password, self.password)
    
    def update_activity(self):
        """Update the last_activity timestamp to now"""
        self.last_activity = timezone.now()
        self.save(update_fields=['last_activity'])
    
    def get_activity_status(self):
        """Return human-readable activity status based on last_activity"""
        if not self.last_activity:
            return "Never logged in"
        
        now = timezone.now()
        time_diff = now - self.last_activity
        
        # Active now (< 5 minutes)
        if time_diff < timedelta(minutes=5):
            return "Active now"
        
        # Minutes ago (5-59 minutes)
        if time_diff < timedelta(hours=1):
            minutes = int(time_diff.total_seconds() / 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        
        # Hours ago (1-23 hours)
        if time_diff < timedelta(days=1):
            hours = int(time_diff.total_seconds() / 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        
        # Days ago (1-6 days)
        if time_diff < timedelta(days=7):
            days = time_diff.days
            return f"{days} day{'s' if days != 1 else ''} ago"
        
        # Offline (7+ days)
        return "Offline"

    def __str__(self):
        return self.name
class SystemLog(models.Model):
    SEVERITY_CHOICES = [
        ('Info', 'Info'),
        ('Warning', 'Warning'),
        ('Success', 'Success'),
        ('Error', 'Error'),
    ]

    timestamp = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='logs', null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    action = models.CharField(max_length=255)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='Info')

    def __str__(self):
        return f"{self.timestamp} - {self.user.name if self.user else 'System'} - {self.action}"
