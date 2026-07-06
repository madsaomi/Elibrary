from rest_framework import viewsets

from apps.stats.models import ActionLog
from apps.stats.serializers import ActionLogSerializer


class ActionLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ActionLog.objects.all()
    serializer_class = ActionLogSerializer

    def get_queryset(self):
        qs = ActionLog.objects.all()
        if self.request.user.role == 'school_admin':
            qs = qs.filter(school=self.request.user.school)
        return qs
