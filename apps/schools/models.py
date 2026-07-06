from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from apps.core.models import TimestampMixin, UUIDPrimaryKeyMixin


class District(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    name = models.CharField(max_length=200, verbose_name='Название района')

    class Meta:
        verbose_name = 'Район'
        verbose_name_plural = 'Районы'
        ordering = ('name',)

    def __str__(self):
        return self.name


class School(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    name = models.CharField(max_length=300, verbose_name='Название школы')
    district = models.ForeignKey(
        District, on_delete=models.CASCADE, related_name='schools', verbose_name='Район',
    )

    class Meta:
        verbose_name = 'Школа'
        verbose_name_plural = 'Школы'
        ordering = ('name',)
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'district'],
                name='unique_school_per_district',
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError
        normalized = self.name.strip()
        existing = School.objects.filter(
            name__iexact=normalized, district=self.district,
        ).exclude(pk=self.pk)
        if existing.exists():
            raise ValidationError({'name': 'Школа с таким названием уже существует в этом районе'})

    def save(self, *args, **kwargs):
        self.name = self.name.strip()
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.name} ({self.district.name})'


class Class(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    class Language(models.TextChoices):
        RUSSIAN = 'ru', 'Русский'
        UZBEK = 'uz', 'Узбекский'
        KARAKALPAK = 'kaa', 'Каракалпакский'
        ENGLISH = 'en', 'Английский'

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Активный'
        GRADUATED = 'graduated', 'Выпускник'

    number = models.IntegerField(verbose_name='Номер класса (1-11)', validators=[MinValueValidator(1), MaxValueValidator(11)])
    parallel = models.CharField(max_length=50, verbose_name='Параллель')
    language = models.CharField(max_length=10, choices=Language.choices, verbose_name='Язык обучения')
    academic_year = models.CharField(max_length=20, verbose_name='Учебный год')
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name='classes', verbose_name='Школа',
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, verbose_name='Статус')
    homeroom_teachers = models.ManyToManyField(
        'accounts.User', blank=True, related_name='homeroom_classes', verbose_name='Классные руководители',
    )

    class Meta:
        verbose_name = 'Класс'
        verbose_name_plural = 'Классы'
        ordering = ('school', 'number', 'parallel')
        constraints = [
            models.UniqueConstraint(
                fields=['number', 'parallel', 'language', 'academic_year', 'school'],
                name='unique_class_per_school_year',
            ),
        ]

    def __str__(self):
        return f'{self.number}{self.parallel} ({self.get_language_display()}) - {self.school.name}'


class TransferLog(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    class Status(models.TextChoices):
        DEPARTING = 'departing', 'Ожидает ухода'
        PENDING = 'pending', 'Ожидает перевода'
        COMPLETED = 'completed', 'Завершён'
        CANCELLED = 'cancelled', 'Отменён'

    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='transfers', verbose_name='Пользователь')
    from_school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='transfers_out', verbose_name='Из школы')
    from_grade = models.ForeignKey('Class', on_delete=models.SET_NULL, null=True, blank=True, related_name='transfers_from', verbose_name='Из класса')
    to_school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='transfers_in', verbose_name='В школу', null=True, blank=True)
    initiated_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, related_name='initiated_transfers', verbose_name='Инициировал')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, verbose_name='Статус')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата завершения')
    xp_before = models.IntegerField(default=0, verbose_name='XP до перевода')
    xp_after = models.IntegerField(default=0, verbose_name='XP после перевода')

    class Meta:
        verbose_name = 'Лог перевода'
        verbose_name_plural = 'Логи переводов'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.user} {self.from_school} → {self.to_school} ({self.get_status_display()})'


class PromotionLog(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='promotions', verbose_name='Школа')
    academic_year = models.CharField(max_length=20, verbose_name='Учебный год')
    initiated_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, verbose_name='Инициировал')

    class Meta:
        verbose_name = 'Лог автоперевода'
        verbose_name_plural = 'Логи автопереводов'
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'academic_year'],
                name='unique_promotion_per_school_year',
            ),
        ]

    def __str__(self):
        return f'Перевод {self.school.name} ({self.academic_year})'
