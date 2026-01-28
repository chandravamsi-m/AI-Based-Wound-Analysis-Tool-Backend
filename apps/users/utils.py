import shutil
import os
from django.db import connection
from .models import SystemLog
from django.utils import timezone
from datetime import timedelta

# Record server start time
START_TIME = timezone.now()

def get_uptime():
    """
    Returns the server uptime as a human-readable string.
    """
    now = timezone.now()
    diff = now - START_TIME
    
    days = diff.days
    hours = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60
    
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"

def get_storage_metrics():
    """
    Returns real disk storage metrics using shutil.
    """
    # Get stats for the root directory (or wherever the project is stored)
    total, used, free = shutil.disk_usage("/")
    
    # Convert bytes to GB/TB for human readability
    total_gb = total / (1024**3)
    used_gb = used / (1024**3)
    free_gb = free / (1024**3)
    used_percentage = (used / total) * 100
    
    return {
        'total_capacity_gb': total_gb,
        'used_capacity_gb': used_gb,
        'free_space_gb': free_gb,
        'used_percentage': round(used_percentage, 1),
        'total_capacity_tb': round(total_gb / 1024, 1),
        'used_capacity_tb': round(used_gb / 1024, 1)
    }

def get_database_size():
    """
    Returns the size of the PostgreSQL database in MB/GB.
    Note: Requires PostgreSQL.
    """
    try:
        with connection.cursor() as cursor:
            # This query is specific to PostgreSQL
            cursor.execute("SELECT pg_database_size(current_database())")
            size_bytes = cursor.fetchone()[0]
            
            size_mb = size_bytes / (1024**2)
            size_gb = size_bytes / (1024**3)
            
            return {
                'size_bytes': size_bytes,
                'size_mb': round(size_mb, 2),
                'size_gb': round(size_gb, 2)
            }
    except Exception as e:
        print(f"Error calculating DB size: {e}")
        # Fallback for other DBs or errors
        return {
            'size_bytes': 0,
            'size_mb': 0,
            'size_gb': 0
        }

def log_system_event(user, action, severity='Info', ip_address=None):
    """
    Helper to log system events to the database.
    """
    try:
        SystemLog.objects.create(
            user=user,
            action=action,
            severity=severity,
            ip_address=ip_address,
            timestamp=timezone.now()
        )
    except Exception as e:
        print(f"Failed to log event: {e}")

def get_client_ip(request):
    """
    Extracts IP address from the request object.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
