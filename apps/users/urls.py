from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UserViewSet, LoginView, SystemLogViewSet, DashboardSummaryView

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'logs', SystemLogViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('login/', LoginView.as_view(), name='login'),
    path('dashboard/summary/', DashboardSummaryView.as_view(), name='dashboard-summary'),
]
