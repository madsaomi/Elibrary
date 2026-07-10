from django.core.management.base import BaseCommand
from apps.accounts.models import User
from apps.schools.models import District, School, Class
from apps.gamification.models import Achievement
from apps.gamification.services import ensure_levels


class Command(BaseCommand):
    help = 'Создание тестовых данных для разработки'

    def handle(self, *args, **options):
        if User.objects.filter(login='admin').exists():
            self.stdout.write(self.style.WARNING('Superuser already exists'))
            return

        district, _ = District.objects.get_or_create(name='Test district')
        school, _ = School.objects.get_or_create(name='Test School 1', district=district)
        admin = User.objects.create_superuser(
            login='admin', password='admin123', school=school,
        )
        cl = Class.objects.create(number=1, parallel='A', language='ru', school=school)
        User.objects.create_user(
            login='student1', password='student123',
            role=User.Role.STUDENT, first_name='Ivan', last_name='Ivanov',
            school=school, grade=cl,
        )
        User.objects.create_user(
            login='teacher1', password='teacher123',
            role=User.Role.TEACHER, first_name='Maria', last_name='Petrova',
            school=school, subject='Math',
        )
        ensure_levels()
        self.stdout.write(self.style.SUCCESS(
            'Test data created:\n'
            f'  Superadmin: admin / admin123\n'
            f'  School admin: {admin.login} / admin123\n'
            f'  Student: student1 / student123\n'
            f'  Teacher: teacher1 / teacher123\n'
            f'  School: {school.name}'
        ))
