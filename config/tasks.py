import logging
import json

from celery import shared_task
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


def _call_gemini(prompt, max_retries=2):
    api_key = settings.GEMINI_API_KEY
    if not api_key:
        logger.warning('GEMINI_API_KEY not configured, using fallback questions')
        return None
    model = settings.GEMINI_MODEL
    url = f'https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={api_key}'
    payload = {
        'contents': [{
            'parts': [{'text': prompt}],
        }],
        'generationConfig': {
            'temperature': 0.7,
            'maxOutputTokens': 2048,
        },
    }
    import requests
    for attempt in range(max_retries):
        try:
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                text = data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                return text
            elif resp.status_code == 429:
                logger.warning('Gemini rate limit hit, attempt %d/%d', attempt + 1, max_retries)
                if attempt < max_retries - 1:
                    import time
                    time.sleep(5)
                continue
            else:
                logger.error('Gemini API error %d: %s', resp.status_code, resp.text[:200])
                return None
        except requests.exceptions.RequestException as e:
            logger.error('Gemini request failed: %s', str(e))
            if attempt < max_retries - 1:
                import time
                time.sleep(3)
            continue
    return None


def _parse_questions_from_text(text):
    questions = []
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    q_id = 0
    i = 0
    while i < len(lines) and len(questions) < 15:
        line = lines[i]
        if line and not line.startswith(('A)', 'B)', 'C)', 'Правильный', 'Correct', 'Answer')):
            question_text = line
            options = []
            correct_idx = 0
            for j in range(1, 4):
                if i + j < len(lines):
                    opt = lines[i + j].strip()
                    if opt.startswith(('A)', 'B)', 'C)')):
                        options.append(opt[2:].strip())
                    elif opt.startswith(('Правильный', 'Correct', 'Answer')):
                        answer_text = opt.split(':')[-1].strip() if ':' in opt else opt
                        if 'A' in answer_text.upper():
                            correct_idx = 0
                        elif 'B' in answer_text.upper():
                            correct_idx = 1
                        elif 'C' in answer_text.upper():
                            correct_idx = 2
            if len(options) == 3:
                questions.append({
                    'id': q_id,
                    'question': question_text,
                    'options': options,
                    'correct': correct_idx,
                })
                q_id += 1
                i += 4
                continue
        i += 1
    return questions


def _generate_questions_ai(grade, language):
    lang_prompt = {
        'ru': f'Составь 15 простых вопросов общей эрудиции для учеников {grade} класса. '
              f'Каждый вопрос с 3 вариантами ответа (A, B, C). Укажи правильный ответ. '
              f'Вопросы должны быть под возраст {grade} класса. '
              f'Формат: на каждой строке вопрос, затем A) ответ, B) ответ, C) ответ, '
              f'затем "Правильный: A/B/C". Разделяй группы пустой строкой.',
        'uz': f'{grade}-sinf o\'quvchilari uchun 15 ta oddiy umumiy bilim savoli tuzing. '
              f'Har bir savolga 3 ta variant (A, B, C). To\'g\'ri javobni ko\'rsating. '
              f'Format: savol, keyin A) javob, B) javob, C) javob, '
              f'keyin "To\'g\'ri: A/B/C". Guruhlarni bo\'sh qator bilan ajrating.',
        'kaa': f'{grade}-klass oqıwshıları ushın 15 dana ápiwayı ulıwma bilim sorawı dúziń. '
              f'Hár bir sorawǵa 3 variant (A, B, C). Durıs juwaptı kórsetiń. '
              f'Format: soraw, keyin A) juwap, B) juwap, C) juwap, '
              f'keyin "Durıs: A/B/C". Toparlardı bos qatar menen ajratıń.',
        'en': f'Create 15 simple general knowledge questions for {grade} grade students. '
              f'Each question with 3 options (A, B, C). Indicate the correct answer. '
              f'Questions should be age-appropriate for grade {grade}. '
              f'Format: on each line the question, then A) answer, B) answer, C) answer, '
              f'then "Correct: A/B/C". Separate groups with a blank line.',
    }
    prompt = lang_prompt.get(language, lang_prompt['ru'])
    text = _call_gemini(prompt)
    if text:
        questions = _parse_questions_from_text(text)
        if len(questions) >= 5:
            return questions[:15]
    return None


def _generate_fallback_questions(grade, language):
    fallback_sets = {
        5: {'ru': [('Столица Узбекистана?', ['Ташкент', 'Самарканд', 'Бухара'], 0),
                   ('Сколько континентов на Земле?', ['5', '6', '7'], 2),
                   ('Самая длинная река в мире?', ['Нил', 'Амазонка', 'Миссисипи'], 0)]},
    }
    grade_set = fallback_sets.get(grade, {})
    lang_set = grade_set.get(language, fallback_sets.get(5, {}).get('ru', []))
    questions = []
    for i, (q, opts, correct) in enumerate(lang_set):
        questions.append({'id': i, 'question': q, 'options': opts, 'correct': correct})
    # Fill remaining with generic questions
    subjects = ['математика', 'география', 'история', 'биология', 'литература']
    for j in range(len(questions), 15):
        idx = j % len(subjects)
        questions.append({
            'id': j,
            'question': f'Вопрос по {subjects[idx]} для {grade} класса',
            'options': ['Вариант A', 'Вариант B', 'Вариант C'],
            'correct': 0,
        })
    return questions


@shared_task
def generate_weekly_challenges():
    from apps.gamification.models import Challenge
    from apps.schools.models import Class
    from datetime import timedelta
    today = timezone.now().date()
    monday = today - timedelta(days=today.weekday())

    grades = Class.objects.filter(status=Class.Status.ACTIVE).values_list('number', flat=True).distinct()
    languages = ['ru', 'uz', 'kaa', 'en']

    for grade in grades:
        for lang in languages:
            questions = _generate_questions_ai(grade, lang)
            if not questions:
                questions = _generate_fallback_questions(grade, lang)
            Challenge.objects.get_or_create(
                grade_number=grade,
                language=lang,
                week_start=monday,
                defaults={
                    'questions': questions,
                    'status': Challenge.Status.DRAFT,
                },
            )


@shared_task
def auto_promote_classes():
    from apps.schools.services import auto_promote_classes as promote_service
    from apps.schools.models import School
    from datetime import timedelta

    today = timezone.now().date()
    if today.month != 9 or today.day != 1:
        return

    current_year = f'{today.year - 1}-{today.year}'
    next_year = f'{today.year}-{today.year + 1}'

    schools = School.objects.all()
    for school in schools:
        if Class.objects.filter(school=school, academic_year=next_year).exists():
            continue
        promote_service(school, current_year, next_year)
