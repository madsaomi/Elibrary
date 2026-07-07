from django.urls import path
from apps.core.views import healthcheck

urlpatterns = [
    path('', healthcheck, name='healthcheck'),
]
