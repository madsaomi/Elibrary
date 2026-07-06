from rest_framework import viewsets

from apps.notifications.models import News
from apps.notifications.serializers import NewsSerializer


class NewsViewSet(viewsets.ModelViewSet):
    queryset = News.objects.all()
    serializer_class = NewsSerializer

    def get_queryset(self):
        from .services import NewsService
        return NewsService.visible_to(self.request.user)
