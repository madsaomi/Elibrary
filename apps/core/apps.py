from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    label = 'core'

    def ready(self):
        try:
            from django_celery_beat.models import PeriodicTask, CrontabSchedule
            import json
            schedule_weekly, _ = CrontabSchedule.objects.get_or_create(
                minute='0', hour='8', day_of_week='1', day_of_month='*', month_of_year='*',
            )
            PeriodicTask.objects.get_or_create(
                name='Generate weekly challenges',
                defaults={
                    'crontab': schedule_weekly,
                    'task': 'apps.gamification.tasks.generate_weekly_challenges',
                    'kwargs': json.dumps({}),
                },
            )
            schedule_yearly, _ = CrontabSchedule.objects.get_or_create(
                minute='0', hour='3', day_of_week='*', day_of_month='1', month_of_year='9',
            )
            PeriodicTask.objects.get_or_create(
                name='Auto-promote classes',
                defaults={
                    'crontab': schedule_yearly,
                    'task': 'config.tasks.auto_promote_classes',
                    'kwargs': json.dumps({}),
                },
            )
        except Exception as e:
            logger.warning('Failed to setup periodic tasks: %s', e)
