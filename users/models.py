from django.db import models
from django.contrib.auth.hashers import make_password, check_password

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
    activity = models.CharField(max_length=50, blank=True)
    isActive = models.BooleanField(default=True)

    def set_password(self, raw_password):
        """Hash and set the password"""
        self.password = make_password(raw_password)

    def verify_password(self, raw_password):
        """Check if the provided password matches the hashed password"""
        return check_password(raw_password, self.password)

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
