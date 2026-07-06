from django.db import models

from apps.core.models import UUIDPrimaryKeyMixin, TimestampMixin, SchoolScopedModel


class ActionLog(SchoolScopedModel, UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    class ActionType(models.TextChoices):
        LOGIN = 'login', 'Вход'
        LOGOUT = 'logout', 'Выход'
        LOAN = 'loan', 'Выдача'
        RETURN = 'return', 'Возврат'
        FORCED_RETURN = 'forced_return', 'Принудительный возврат'
        USER_CREATED = 'user_created', 'Создание пользователя'
        PASSWORD_RESET = 'password_reset', 'Сброс пароля'
        TRANSFER = 'transfer', 'Перевод'

    user = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, verbose_name='Пользователь')
    action = models.CharField(max_length=50, choices=ActionType.choices, verbose_name='Действие')
    details = models.JSONField(default=dict, blank=True, verbose_name='Детали')

    class Meta:
        verbose_name = 'Лог действия'
        verbose_name_plural = 'Логи действий'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.user} — {self.get_action_display()}'
