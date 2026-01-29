from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AlertViewSet, 
    AlertStatsView, 
    DoctorDashboardSummaryView, 
    DoctorScheduledTasksView, 
    WoundStatsView
)

router = DefaultRouter()
router.register(r'alerts', AlertViewSet, basename='alert')

urlpatterns = [
    path('', include(router.urls)),
    path('alert-stats/', AlertStatsView.as_view(), name='alert-stats'),
    path('doctor/summary/', DoctorDashboardSummaryView.as_view(), name='doctor-summary'),
    path('doctor/schedule/', DoctorScheduledTasksView.as_view(), name='doctor-schedule'),
    path('doctor/stats/', WoundStatsView.as_view(), name='doctor-stats'),
]
