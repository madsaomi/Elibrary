from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    label = 'core'

    def ready(self):
        try:
            from config.beat_schedule import setup_periodic_tasks
            setup_periodic_tasks()
        except Exception as e:
            logger.warning('Failed to setup periodic tasks: %s', e)
