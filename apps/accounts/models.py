from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.accounts.managers import UserManager


class User(AbstractUser):
    class Role(models.TextChoices):
        SUPERADMIN = 'superadmin', 'Суперадмин'
        SCHOOL_ADMIN = 'school_admin', 'Школьный админ'
        TEACHER = 'teacher', 'Учитель'
        STUDENT = 'student', 'Ученик'

    username = None
    email = None

    login = models.CharField(max_length=150, unique=True, null=True, blank=True, verbose_name='Логин')
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STUDENT, db_index=True, verbose_name='Роль')
    school = models.ForeignKey(
        'schools.School',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        db_index=True,
        verbose_name='Школа',
    )
    subject = models.CharField(max_length=100, blank=True, verbose_name='Предмет')
    grade = models.ForeignKey(
        'schools.Class',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='grade_users',
        verbose_name='Класс',
    )
    is_active_for_gamification = models.BooleanField(default=False, verbose_name='Участвует в геймификации')
    transfer_status = models.CharField(
        max_length=20, blank=True, default='',
        choices=[
            ('', 'Не в переводе'),
            ('departing', 'Ожидает ухода'),
            ('pending', 'Ожидает перевода'),
            ('completed', 'Переведён'),
        ],
        verbose_name='Статус перевода',
    )

    USERNAME_FIELD = 'login'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        login_part = self.login or 'нет логина'
        return f'{self.get_full_name()} ({login_part})'
