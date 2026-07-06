import uuid

from django.db import models

from apps.core.managers import SchoolScopedManager


class UUIDPrimaryKeyMixin(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimestampMixin(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SchoolScopedModel(models.Model):
    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        related_name='%(class)s_set',
    )

    objects = SchoolScopedManager()

    class Meta:
        abstract = True

    @classmethod
    def for_user(cls, user):
        return cls.objects.for_user(user)
