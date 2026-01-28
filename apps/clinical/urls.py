from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AlertViewSet, AlertStatsView

router = DefaultRouter()
router.register(r'alerts', AlertViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('alert-stats/', AlertStatsView.as_view(), name='alert-stats'),
]
