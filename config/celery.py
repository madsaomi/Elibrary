import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
app = Celery('config')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

from celery.schedules import crontab

app.conf.beat_schedule = {
    'generate-weekly-challenges-sunday-night': {
        'task': 'apps.gamification.tasks.generate_weekly_challenges',
        'schedule': crontab(hour=23, minute=0, day_of_week=0),  # Каждое воскресенье в 23:00
    },
}
