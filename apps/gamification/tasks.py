import logging
from celery import shared_task
from django.utils import timezone
import datetime

from apps.gamification.models import Challenge
from apps.gamification.services import generate_challenge_questions
from apps.accounts.models import User
from apps.schools.models import Class

logger = logging.getLogger(__name__)

@shared_task
def generate_weekly_challenges():
    """
    Фоновая задача для генерации еженедельных челленджей.
    Генерирует уникальные тесты для комбинации (Школа, Класс, Язык),
    если в этой школе есть активные ученики этого класса.
    """
    # Определяем ближайший понедельник
    today = timezone.now().date()
    days_ahead = 0 - today.weekday()
    if days_ahead <= 0: # Target is in the next week
        days_ahead += 7
    next_monday = today + datetime.timedelta(days=days_ahead)
    
    logger.info(f"Начало генерации челленджей на неделю с {next_monday}")
    
    # Находим все классы (5-11), в которых есть хотя бы один ученик
    # Сначала найдем активных учеников 5-11 классов
    active_students = User.objects.filter(
        role=User.Role.STUDENT,
        is_active_for_gamification=True,
        grade__number__gte=5,
        grade__number__lte=11
    ).select_related('school', 'grade')
    
    # Собираем уникальные комбинации: (school_id, grade_number, language)
    combinations = set()
    for student in active_students:
        if student.school and student.grade:
            combinations.add((student.school, student.grade.number, student.grade.language))
            
    created_count = 0
    error_count = 0
    
    for school, grade_number, language in combinations:
        # Проверяем, есть ли уже опубликованный челлендж для этой комбинации на эту неделю
        exists = Challenge.objects.filter(
            school=school,
            grade_number=grade_number,
            language=language,
            week_start=next_monday,
            status=Challenge.Status.PUBLISHED
        ).exists()
        
        if exists:
            continue
            
        try:
            logger.info(f"Генерация для школы {school.name}, {grade_number} класс, {language}...")
            questions = generate_challenge_questions(grade_number, language)
            
            Challenge.objects.create(
                school=school,
                grade_number=grade_number,
                language=language,
                week_start=next_monday,
                questions=questions,
                status=Challenge.Status.PUBLISHED
            )
            created_count += 1
            logger.info(f"Успешно сгенерировано.")
        except Exception as e:
            logger.error(f"Ошибка генерации для {school.name} ({grade_number}, {language}): {e}")
            error_count += 1
            
    logger.info(f"Генерация завершена. Создано: {created_count}, Ошибок: {error_count}")
    return f"Created: {created_count}, Errors: {error_count}"
