import json
from django.core.management.base import BaseCommand
from apps.gamification.models import Achievement

class Command(BaseCommand):
    help = 'Инициализация списка достижений в базе данных'

    def handle(self, *args, **options):
        achievements = [
            {
                'code': 'streak_7',
                'name': 'Читатель недели',
                'description': 'Заработать стрик 7 дней подряд',
                'icon_emoji': '🔥',
                'category': Achievement.Category.STREAK,
                'condition': {'field': 'streak', 'gte': 7}
            },
            {
                'code': 'streak_30',
                'name': 'Месяц с книгой',
                'description': 'Заработать стрик 30 дней подряд',
                'icon_emoji': '🗓️',
                'category': Achievement.Category.STREAK,
                'condition': {'field': 'streak', 'gte': 30}
            },
            {
                'code': 'xp_100',
                'name': 'Новичиок',
                'description': 'Накопить первые 100 XP',
                'icon_emoji': '🌱',
                'category': Achievement.Category.XP,
                'condition': {'field': 'total_xp', 'gte': 100}
            },
            {
                'code': 'xp_1000',
                'name': 'Первая тысяча',
                'description': 'Накопить 1000 XP',
                'icon_emoji': '⭐',
                'category': Achievement.Category.XP,
                'condition': {'field': 'total_xp', 'gte': 1000}
            },
            {
                'code': 'xp_10000',
                'name': 'Ветеран библиотеки',
                'description': 'Накопить 10000 XP',
                'icon_emoji': '👑',
                'category': Achievement.Category.XP,
                'condition': {'field': 'total_xp', 'gte': 10000}
            },
            {
                'code': 'first_book',
                'name': 'Первый шаг',
                'description': 'Сдать первую прочитанную книгу вовремя',
                'icon_emoji': '📖',
                'category': Achievement.Category.BOOKS,
                'condition': {'field': 'books_returned', 'gte': 1}
            },
            {
                'code': 'bookworm_50',
                'name': 'Книжный червь',
                'description': 'Прочитать и вернуть 50 книг',
                'icon_emoji': '📚',
                'category': Achievement.Category.BOOKS,
                'condition': {'field': 'books_returned', 'gte': 50}
            },
        ]

        count_created = 0
        count_updated = 0

        for ach_data in achievements:
            obj, created = Achievement.objects.update_or_create(
                code=ach_data['code'],
                defaults={
                    'name': ach_data['name'],
                    'description': ach_data['description'],
                    'icon_emoji': ach_data['icon_emoji'],
                    'category': ach_data['category'],
                    'condition': ach_data['condition']
                }
            )
            if created:
                count_created += 1
            else:
                count_updated += 1

        self.stdout.write(self.style.SUCCESS(f'Успешно инициализировано достижений. Создано: {count_created}, Обновлено: {count_updated}'))
