import uuid

from django.db import models
from django.utils import timezone
from apps.schools.models import Class

from apps.core.models import UUIDPrimaryKeyMixin, TimestampMixin, SchoolScopedModel


class XPTransaction(SchoolScopedModel, UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    class Reason(models.TextChoices):
        RETURN_ON_TIME = 'return_ontime', 'Возврат вовремя'
        RETURN_LATE = 'return_late', 'Возврат с опозданием'
        COMEBACK_BONUS = 'comeback_bonus', 'Камбэк-бонус'
        CHALLENGE = 'challenge', 'Челлендж'
        STREAK = 'streak', 'Стрик'
        ACHIEVEMENT = 'achievement', 'Достижение'

    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, db_index=True, related_name='xp_transactions', verbose_name='Пользователь')
    amount = models.IntegerField(verbose_name='Количество XP')
    reason = models.CharField(max_length=50, db_index=True, choices=Reason.choices, verbose_name='Причина')

    class Meta:
        verbose_name = 'XP транзакция'
        verbose_name_plural = 'XP транзакции'
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.user.get_full_name()}: {self.amount} XP ({self.get_reason_display()})'


class Level(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    number = models.IntegerField(unique=True, verbose_name='Номер уровня')
    xp_required = models.IntegerField(verbose_name='XP для достижения')
    bonus_percent = models.IntegerField(default=0, verbose_name='Бонус XP в %')

    class Meta:
        verbose_name = 'Уровень'
        verbose_name_plural = 'Уровни'
        ordering = ('number',)

    def __str__(self):
        return f'Уровень {self.number} ({self.xp_required} XP)'


class UserLevel(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    user = models.OneToOneField('accounts.User', on_delete=models.CASCADE, related_name='level_info', verbose_name='Пользователь')
    level = models.ForeignKey(Level, on_delete=models.CASCADE, verbose_name='Уровень')
    total_xp = models.IntegerField(default=0, verbose_name='Всего XP')

    class Meta:
        verbose_name = 'Уровень пользователя'
        verbose_name_plural = 'Уровни пользователей'

    def __str__(self):
        return f'{self.user.get_full_name()} — Ур. {self.level.number}'


class Achievement(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    class Category(models.TextChoices):
        STREAK = 'streak', 'Стрик'
        BOOKS = 'books', 'Книги'
        XP = 'xp', 'XP'
        CHALLENGE = 'challenge', 'Челлендж'

    code = models.CharField(max_length=100, unique=True, verbose_name='Код')
    name = models.CharField(max_length=200, verbose_name='Название')
    description = models.TextField(blank=True, verbose_name='Описание')
    icon_emoji = models.CharField(max_length=10, blank=True, verbose_name='Emoji')
    category = models.CharField(max_length=20, choices=Category.choices, verbose_name='Категория')

    class Meta:
        verbose_name = 'Достижение'
        verbose_name_plural = 'Достижения'

    def __str__(self):
        return f'{self.icon_emoji} {self.name}'


class UserAchievement(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='achievements', verbose_name='Пользователь')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE, verbose_name='Достижение')
    awarded_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата получения')

    class Meta:
        verbose_name = 'Достижение пользователя'
        verbose_name_plural = 'Достижения пользователей'
        constraints = [
            models.UniqueConstraint(fields=['user', 'achievement'], name='unique_user_achievement'),
        ]

    def __str__(self):
        return f'{self.user.get_full_name()} → {self.achievement.name}'


class Streak(SchoolScopedModel, UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    user = models.OneToOneField('accounts.User', on_delete=models.CASCADE, related_name='streak', verbose_name='Пользователь')
    current_streak = models.IntegerField(default=0, verbose_name='Текущий стрик')
    longest_streak = models.IntegerField(default=0, verbose_name='Максимальный стрик')
    last_activity_date = models.DateField(null=True, blank=True, verbose_name='Последняя активность')
    frozen_days = models.IntegerField(default=0, verbose_name='Заморозки стрика')

    class Meta:
        verbose_name = 'Стрик'
        verbose_name_plural = 'Стрики'

    def __str__(self):
        return f'{self.user.get_full_name()}: {self.current_streak} дней'


class Challenge(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Черновик'
        PUBLISHED = 'published', 'Опубликован'
        CLOSED = 'closed', 'Закрыт'

    school = models.ForeignKey('schools.School', on_delete=models.CASCADE, null=True, blank=True, related_name='challenges', verbose_name='Школа')
    grade_number = models.IntegerField(verbose_name='Класс')
    language = models.CharField(max_length=10, choices=Class.Language.choices, verbose_name='Язык')
    week_start = models.DateField(verbose_name='Начало недели')
    questions = models.JSONField(default=list, verbose_name='Вопросы')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, verbose_name='Статус')

    class Meta:
        verbose_name = 'Челлендж'
        verbose_name_plural = 'Челленджи'
        ordering = ('-week_start',)
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'grade_number', 'language', 'week_start'],
                name='unique_challenge_per_week',
            ),
        ]

    def __str__(self):
        return f'Челлендж {self.grade_number} кл. ({self.week_start})'


class ChallengeAttempt(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, db_index=True, related_name='attempts', verbose_name='Челлендж')
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, db_index=True, related_name='challenge_attempts', verbose_name='Пользователь')
    started_at = models.DateTimeField(auto_now_add=True, verbose_name='Начало')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Завершение')
    answers = models.JSONField(default=dict, verbose_name='Ответы')
    score = models.IntegerField(default=0, verbose_name='Баллы')
    question_order = models.JSONField(default=list, verbose_name='Порядок вопросов')
    is_completed = models.BooleanField(default=False, verbose_name='Завершён')
    time_limit_minutes = models.IntegerField(default=15, verbose_name='Лимит времени (мин)')

    class Meta:
        verbose_name = 'Попытка челленджа'
        verbose_name_plural = 'Попытки челленджей'
        constraints = [
            models.UniqueConstraint(fields=['challenge', 'user'], name='unique_challenge_attempt'),
        ]

    def __str__(self):
        return f'{self.user.get_full_name()} — {self.score}/{len(self.answers or {})}'
