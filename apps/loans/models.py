import uuid

from django.db import models
from django.utils import timezone

from apps.catalog.models import Textbook, RegularBook
from apps.core.models import UUIDPrimaryKeyMixin, TimestampMixin, SchoolScopedModel


def _default_due_date():
    return timezone.now().date() + timezone.timedelta(days=30)


class TextbookLoan(SchoolScopedModel, UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Выдан'
        RETURNED = 'returned', 'Возвращён'
        OVERDUE = 'overdue', 'Просрочен'
        FORCED = 'forced', 'Принудительный возврат'

    textbook = models.ForeignKey(Textbook, on_delete=models.CASCADE, related_name='loans', verbose_name='Учебник')
    student = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='textbook_loans', verbose_name='Ученик',
    )
    borrower_type = models.CharField(
        max_length=10, choices=[('student', 'Ученик'), ('teacher', 'Учитель')],
        default='student', verbose_name='Тип заёмщика',
    )
    issued_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='issued_textbooks', verbose_name='Выдал',
    )
    issued_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата выдачи')
    due_date = models.DateField(verbose_name='Срок возврата')
    returned_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата возврата')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, verbose_name='Статус')

    class Meta:
        verbose_name = 'Выдача учебника'
        verbose_name_plural = 'Выдачи учебников'
        ordering = ('-issued_at',)

    def __str__(self):
        return f'{self.textbook.title} → {self.student.get_full_name()}'


class RegularBookLoan(SchoolScopedModel, UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Выдана'
        RETURNED = 'returned', 'Возвращена'
        FORCED = 'forced', 'Принудительный возврат'

    book = models.ForeignKey(RegularBook, on_delete=models.CASCADE, related_name='loans', verbose_name='Книга')
    user = models.ForeignKey(
        'accounts.User', on_delete=models.CASCADE, related_name='book_loans', verbose_name='Пользователь',
    )
    issued_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='issued_books', verbose_name='Выдал',
    )
    issued_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата выдачи')
    due_date = models.DateField(default=_default_due_date, verbose_name='Срок возврата')
    returned_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата возврата')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, verbose_name='Статус')
    qr_token = models.CharField(max_length=500, blank=True, verbose_name='QR-токен')

    class Meta:
        verbose_name = 'Выдача книги'
        verbose_name_plural = 'Выдачи книг'
        ordering = ('-issued_at',)

    def __str__(self):
        return f'{self.book.title} → {self.user.get_full_name()}'
