from rest_framework import viewsets

from apps.notifications.models import News
from apps.notifications.serializers import NewsSerializer
from api.v1.permissions import IsSchoolAdminOrSuperAdmin


class NewsViewSet(viewsets.ModelViewSet):
    queryset = News.objects.all()
    serializer_class = NewsSerializer
    permission_classes = [IsSchoolAdminOrSuperAdmin]

    def get_queryset(self):
        from .services import NewsService
        return NewsService.visible_to(self.request.user)
