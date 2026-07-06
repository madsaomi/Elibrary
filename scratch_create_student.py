import os
import django

# Setup django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.accounts.models import User
from apps.schools.models import School, District, Class

# Create district
district, _ = District.objects.get_or_create(name='Тестовый район')

# Create school
school, _ = School.objects.get_or_create(
    name='Школа №1',
    defaults={'district': district}
)

# Create class
grade, _ = Class.objects.get_or_create(
    school=school,
    number=8,
    parallel='А',
    language='ru'
)

# Create student
student_login = 'student_test'
student = User.objects.filter(login=student_login).first()

if not student:
    student = User.objects.create_user(
        login=student_login,
        password='password123',
        role=User.Role.STUDENT,
        first_name='Иван',
        last_name='Иванов',
        school=school,
        grade=grade,
        is_active_for_gamification=True
    )
    print(f"✅ Создан ученик:\nЛогин: {student_login}\nПароль: password123\nКласс: {grade}")
else:
    # reset password just in case
    student.set_password('password123')
    student.save()
    print(f"ℹ️ Ученик {student_login} уже существует. Пароль сброшен на password123.")
