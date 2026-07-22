from django.db import models, transaction
from django.utils import timezone

from apps.gamification.models import (
    XPTransaction, Level, UserLevel, Achievement, UserAchievement,
    Streak, Challenge, ChallengeAttempt,
)
from apps.accounts.models import User


LEVELS = [
    {'number': 1, 'xp_required': 0, 'bonus_percent': 0},
    {'number': 2, 'xp_required': 100, 'bonus_percent': 2},
    {'number': 3, 'xp_required': 250, 'bonus_percent': 4},
    {'number': 4, 'xp_required': 500, 'bonus_percent': 6},
    {'number': 5, 'xp_required': 1000, 'bonus_percent': 8},
    {'number': 6, 'xp_required': 2000, 'bonus_percent': 10},
    {'number': 7, 'xp_required': 4000, 'bonus_percent': 12},
    {'number': 8, 'xp_required': 8000, 'bonus_percent': 14},
    {'number': 9, 'xp_required': 15000, 'bonus_percent': 16},
    {'number': 10, 'xp_required': 30000, 'bonus_percent': 20},
]


@transaction.atomic
def ensure_levels():
    for lvl in LEVELS:
        Level.objects.get_or_create(number=lvl['number'], defaults=lvl)


@transaction.atomic
def award_freeze_days(user, days=1, school=None):
    streak, _ = Streak.objects.get_or_create(user=user, school=school or user.school)
    streak.frozen_days += days
    streak.save()
    return streak


@transaction.atomic
def update_user_level(user_level):
    correct_level = Level.objects.filter(xp_required__lte=user_level.total_xp).order_by('-xp_required').first()
    if correct_level and user_level.level != correct_level:
        user_level.level = correct_level
        user_level.save(update_fields=['level'])


@transaction.atomic
def add_xp(user, amount, reason, school=None):
    if not user.is_active_for_gamification:
        return
    from django.db.models import F
    if amount <= 0:
        return
    user_level, _ = UserLevel.objects.get_or_create(user=user, defaults={'level': Level.objects.first(), 'total_xp': 0})
    # Применяем бонус за уровень (bonus_percent)
    bonus = user_level.level.bonus_percent
    effective_amount = amount + int(amount * bonus / 100)
    XPTransaction.objects.create(user=user, amount=effective_amount, reason=reason, school=school or user.school)
    UserLevel.objects.filter(pk=user_level.pk).update(total_xp=F('total_xp') + effective_amount)
    user_level.refresh_from_db()
    update_user_level(user_level)
    check_achievements(user)


@transaction.atomic
def award_comeback_bonus(user, school=None):
    if not user.is_active_for_gamification:
        return None
    last_late = XPTransaction.objects.filter(user=user, reason=XPTransaction.Reason.RETURN_LATE).order_by('-created_at').first()
    last_ontime = XPTransaction.objects.filter(user=user, reason__in=[XPTransaction.Reason.RETURN_ON_TIME, XPTransaction.Reason.COMEBACK_BONUS]).order_by('-created_at').first()
    if not last_late:
        return None
    if last_ontime and last_ontime.created_at > last_late.created_at:
        return None
    bonus_amount = 30
    if school is None:
        school = user.school
    tx = XPTransaction.objects.create(user=user, amount=bonus_amount, reason=XPTransaction.Reason.COMEBACK_BONUS, school=school)
    user_level, _ = UserLevel.objects.get_or_create(user=user, defaults={'level': Level.objects.first() or Level.objects.create(number=1, xp_required=0, bonus_percent=0)})
    from django.db.models import F
    UserLevel.objects.filter(pk=user_level.pk).update(total_xp=F('total_xp') + bonus_amount)
    user_level.refresh_from_db()
    update_user_level(user_level)
    return tx


@transaction.atomic
def check_achievements(user):
    if not user.is_active_for_gamification:
        return
    ul = UserLevel.objects.filter(user=user).first()
    total_xp = ul.total_xp if ul else 0
    streak = getattr(user, 'streak', None)
    current_streak = streak.current_streak if streak else 0

    achievements_to_check = [
        {'code': 'xp_100', 'condition': {'field': 'total_xp', 'gte': 100}, 'xp_reward': 10},
        {'code': 'xp_1000', 'condition': {'field': 'total_xp', 'gte': 1000}, 'xp_reward': 50},
        {'code': 'xp_10000', 'condition': {'field': 'total_xp', 'gte': 10000}, 'xp_reward': 500},
        {'code': 'streak_7', 'condition': {'field': 'streak', 'gte': 7}, 'xp_reward': 50},
        {'code': 'streak_30', 'condition': {'field': 'streak', 'gte': 30}, 'xp_reward': 150},
        {'code': 'first_book', 'condition': {'field': 'books_returned', 'gte': 1}, 'xp_reward': 20},
        {'code': 'bookworm_50', 'condition': {'field': 'books_returned', 'gte': 50}, 'xp_reward': 200},
    ]

    codes = [a['code'] for a in achievements_to_check]
    achievements = {a.code: a for a in Achievement.objects.filter(code__in=codes)}
    earned = set(UserAchievement.objects.filter(
        user=user, achievement__code__in=codes
    ).values_list('achievement__code', flat=True))

    books_returned = user.book_loans.filter(status='returned').count()
    for ach_config in achievements_to_check:
        ach = achievements.get(ach_config['code'])
        if not ach:
            continue
        if ach_config['code'] in earned:
            continue
        cond = ach_config['condition']
        field = cond['field']
        threshold = cond['gte']
        actual = {'total_xp': total_xp, 'streak': current_streak, 'books_returned': books_returned}.get(field, 0)
        if actual >= threshold:
            UserAchievement.objects.create(user=user, achievement=ach)
            add_xp(user, ach_config.get('xp_reward', 50), XPTransaction.Reason.ACHIEVEMENT)


@transaction.atomic
def update_streak(user):
    if not user.is_active_for_gamification:
        return None
    today = timezone.now().date()
    streak, _ = Streak.objects.get_or_create(user=user, school=user.school)
    if streak.last_activity_date == today:
        return streak
    if streak.last_activity_date == today - timezone.timedelta(days=1):
        streak.current_streak += 1
    elif streak.frozen_days > 0 and streak.last_activity_date and streak.last_activity_date < today - timezone.timedelta(days=1):
        streak.frozen_days -= 1
        streak.current_streak += 1
    else:
        streak.current_streak = 1
    streak.last_activity_date = today
    streak.longest_streak = max(streak.longest_streak, streak.current_streak)
    streak.save()
    return streak


def generate_challenge_questions(grade_number, language):
    """
    Генерирует 15 вопросов для челленджа через API Gemini.
    Возвращает список словарей: [{'question': '...', 'options': ['A', 'B', 'C'], 'correct_index': 0}, ...]
    """
    import json
    from django.conf import settings
    
    api_key = getattr(settings, 'GEMINI_API_KEY', '')
    if not api_key:
        raise ValueError("GEMINI_API_KEY не настроен")
        
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise ImportError("Установите google-genai: pip install google-genai")
        
    client = genai.Client(api_key=api_key)
    
    lang_name = {
        'ru': 'русском',
        'uz': 'узбекском',
        'kaa': 'каракалпакском',
        'en': 'английском'
    }.get(language, 'русском')
    
    prompt = f"""
    Сгенерируй ровно 15 тестовых вопросов на общую эрудицию для школьников {grade_number} класса.
    Вопросы должны быть на {lang_name} языке.
    Тематика: общая эрудиция (наука, природа, география, история, литература).
    Сложность: подходит для возраста учеников {grade_number} класса.
    Каждый вопрос должен иметь ровно 3 варианта ответа.
    
    Верни результат СТРОГО в формате JSON-массива без markdown форматирования (без ```json ... ```), 
    где каждый элемент это объект:
    {{
        "question": "Текст вопроса?",
        "options": ["Вариант 1", "Вариант 2", "Вариант 3"],
        "correct_index": 0
    }}
    Где correct_index — это индекс правильного ответа (0, 1 или 2) в массиве options.
    """
    
    model_name = getattr(settings, 'GEMINI_MODEL', 'gemini-2.0-flash')
    
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
        timeout=60,
    )
    
    text = response.text.strip()
    # Удаляем возможные markdown блоки, если ИИ всё же их вернул
    if text.startswith('```json'):
        text = text[7:]
    if text.startswith('```'):
        text = text[3:]
    if text.endswith('```'):
        text = text[:-3]
        
    try:
        questions = json.loads(text.strip())
        if not isinstance(questions, list) or len(questions) == 0:
            raise ValueError("API вернул невалидный массив вопросов")
        return questions
    except json.JSONDecodeError as e:
        raise ValueError(f"Ошибка парсинга JSON от ИИ: {e}\nОтвет ИИ: {text}")
