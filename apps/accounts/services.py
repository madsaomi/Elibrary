import secrets
import string

from django.contrib.auth import authenticate, login as django_login, logout as django_logout
from django.contrib.auth.hashers import make_password
from django.db import transaction

from apps.accounts.models import User
from apps.schools.models import Class


def generate_password(length=12):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


_CYRILLIC_TO_LATIN = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'E',
    'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
    'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
    'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shch',
    'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
    'ў': 'o', 'қ': 'q', 'ғ': 'gh', 'ҳ': 'h', 'Ў': 'O', 'Қ': 'Q', 'Ғ': 'Gh', 'Ҳ': 'H',
    'ә': 'a', 'ө': 'o', 'ү': 'u', 'і': 'i', 'ң': 'n', 'Ә': 'A', 'Ө': 'O', 'Ү': 'U', 'І': 'I', 'Ң': 'N',
}


def to_latin(text):
    return ''.join(_CYRILLIC_TO_LATIN.get(c, c) for c in text)


def is_latin(text):
    allowed = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-.')
    return all(c in allowed for c in text)


def generate_login(first_name, last_name, school_id):
    base = f'{to_latin(first_name).lower()}.{to_latin(last_name).lower()}'
    login = base
    suffix = 1
    while User.objects.filter(login=login).exists() and suffix < 1000:
        login = f'{base}{suffix}'
        suffix += 1
    if suffix >= 1000:
        login = f'{base}.{secrets.token_hex(4)}'
    return login


@transaction.atomic
def create_user(role, first_name, last_name, school, grade=None, subject='', password=None):
    login = generate_login(first_name, last_name, school.id)
    if not password:
        password = generate_password()
    user = User(
        login=login,
        first_name=to_latin(first_name),
        last_name=to_latin(last_name),
        role=role,
        school=school,
        grade=grade,
        subject=subject,
    )
    user.set_password(password)
    user.save()
    return user, password


@transaction.atomic
def reset_password(user):
    new_password = generate_password()
    user.set_password(new_password)
    user.save()
    return new_password


def auth_login(request, login, password):
    user = authenticate(request, username=login, password=password)
    if user is not None:
        django_login(request, user)
    return user


def auth_logout(request):
    django_logout(request)


@transaction.atomic
def activate_grade_access(school, grade_number, academic_year):
    classes = Class.objects.filter(school=school, number=grade_number, academic_year=academic_year)
    results = []
    students = User.objects.filter(
        role=User.Role.STUDENT, grade__in=list(classes), school=school
    ).select_for_update()
    for student in students:
        if not student.login:
            student.login = generate_login(student.first_name or 'student', student.last_name or str(student.id), school.id)
        if not student.has_usable_password():
            password = generate_password()
            student.set_password(password)
        else:
            password = None
        student.is_active_for_gamification = True
        student.save()
        results.append({'student': student, 'password': password})
    return results
