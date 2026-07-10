import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def auto_promote_classes():
    from apps.schools.services import auto_promote_classes as promote_service
    from apps.schools.models import School, Class
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
