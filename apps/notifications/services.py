from django.db.models import Q

from .models import News


class NewsService:
    @staticmethod
    def visible_to(user):
        if user.is_superuser or user.role == 'superadmin':
            return News.objects.all()
        if user.role == 'school_admin':
            return News.objects.filter(
                Q(author_level=News.AuthorLevel.SUPERADMIN, school__isnull=True)
                | Q(school=user.school)
            )
        return News.objects.filter(school=user.school, is_published=True)
