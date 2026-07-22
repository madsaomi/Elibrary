from django.db import models

from apps.core.models import UUIDPrimaryKeyMixin, TimestampMixin


class News(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    class AuthorLevel(models.TextChoices):
        SUPERADMIN = 'superadmin', 'Суперадмин'
        SCHOOL_ADMIN = 'school_admin', 'Школьный админ'

    title = models.CharField(max_length=300, verbose_name='Заголовок')
    content = models.TextField(verbose_name='Содержание')
    author = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='news_author', verbose_name='Автор')
    author_level = models.CharField(max_length=20, choices=AuthorLevel.choices, verbose_name='Уровень автора')
    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, null=True, blank=True, db_index=True, related_name='school_news', verbose_name='Школа')
    is_published = models.BooleanField(default=False, verbose_name='Опубликовано')
    published_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата публикации')

    class Meta:
        verbose_name = 'Новость'
        verbose_name_plural = 'Новости'
        ordering = ('-created_at',)

    def __str__(self):
        return self.title


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    class Type(models.TextChoices):
        OVERDUE = 'overdue', 'Просрочка'
        ACHIEVEMENT = 'achievement', 'Достижение'
        CHALLENGE = 'challenge', 'Челлендж'
        NEWS = 'news', 'Новость'
        SYSTEM = 'system', 'Системное'

    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, db_index=True, related_name='notifications', verbose_name='Пользователь')
    type = models.CharField(max_length=20, choices=Type.choices, default=Type.SYSTEM, verbose_name='Тип')
    message = models.CharField(max_length=500, verbose_name='Сообщение')
    link = models.CharField(max_length=300, blank=True, verbose_name='Ссылка')
    is_read = models.BooleanField(default=False, db_index=True, verbose_name='Прочитано')

    class Meta:
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
        ordering = ('-created_at',)

    def __str__(self):
        return self.message
