from django.db import models


class SchoolScopedManager(models.Manager):
    def for_user(self, user):
        if user.is_superuser or user.role == 'superadmin':
            return self.get_queryset()
        return self.get_queryset().filter(school=user.school)
