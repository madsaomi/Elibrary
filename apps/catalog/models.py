from django.db import models

from apps.core.models import UUIDPrimaryKeyMixin, TimestampMixin, SchoolScopedModel


class Category(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    name = models.CharField(max_length=200, verbose_name='Название категории')

    class Meta:
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ('name',)

    def __str__(self):
        return self.name


class Textbook(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    title = models.CharField(max_length=300, verbose_name='Название')
    subject = models.CharField(max_length=200, verbose_name='Предмет')
    grade_number = models.IntegerField(verbose_name='Класс')
    language = models.CharField(max_length=10, choices=[
        ('ru', 'Русский'), ('uz', 'Узбекский'), ('kaa', 'Каракалпакский'), ('en', 'Английский'),
    ], verbose_name='Язык')
    academic_year = models.CharField(max_length=20, verbose_name='Учебный год')
    cover = models.ImageField(upload_to='covers/textbooks/', blank=True, verbose_name='Обложка')

    class Meta:
        verbose_name = 'Учебник (справочник)'
        verbose_name_plural = 'Учебники (справочник)'
        ordering = ('subject', 'grade_number')
        constraints = [
            models.UniqueConstraint(
                fields=['title', 'subject', 'grade_number', 'language', 'academic_year'],
                name='unique_textbook',
            ),
        ]

    def __str__(self):
        return f'{self.title} ({self.subject}, {self.grade_number} кл.)'


class SubjectTextbook(UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    school_class = models.ForeignKey(
        'schools.Class', on_delete=models.CASCADE, related_name='subject_textbooks', verbose_name='Класс',
    )
    subject = models.CharField(max_length=200, verbose_name='Предмет')
    textbook = models.ForeignKey(Textbook, on_delete=models.CASCADE, related_name='class_assignments', verbose_name='Учебник')

    class Meta:
        verbose_name = 'Учебник по предмету класса'
        verbose_name_plural = 'Учебники по предметам классов'
        constraints = [
            models.UniqueConstraint(fields=['school_class', 'subject'], name='unique_subject_per_class'),
        ]

    def __str__(self):
        return f'{self.school_class} — {self.subject}: {self.textbook.title}'


class TextbookStock(SchoolScopedModel, UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    textbook = models.ForeignKey(Textbook, on_delete=models.CASCADE, related_name='stocks', verbose_name='Учебник')
    total_copies = models.PositiveIntegerField(default=0, verbose_name='Всего экземпляров')
    available_copies = models.PositiveIntegerField(default=0, verbose_name='Доступно')

    class Meta:
        verbose_name = 'Остаток учебников'
        verbose_name_plural = 'Остатки учебников'
        constraints = [
            models.UniqueConstraint(
                fields=['school', 'textbook'],
                name='unique_stock_per_school',
            ),
        ]

    def __str__(self):
        return f'{self.textbook.title} — {self.school.name} ({self.available_copies}/{self.total_copies})'


class RegularBook(SchoolScopedModel, UUIDPrimaryKeyMixin, TimestampMixin, models.Model):
    title = models.CharField(max_length=300, verbose_name='Название')
    author = models.CharField(max_length=300, blank=True, verbose_name='Автор')
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='books', verbose_name='Категория',
    )
    cover = models.ImageField(upload_to='covers/regular/', blank=True, verbose_name='Обложка')
    total_copies = models.PositiveIntegerField(default=1, verbose_name='Всего экземпляров')
    available_copies = models.PositiveIntegerField(default=1, verbose_name='Доступно')

    class Meta:
        verbose_name = 'Обычная книга'
        verbose_name_plural = 'Обычные книги'
        ordering = ('title',)

    def __str__(self):
        return f'{self.title} — {self.school.name}'
