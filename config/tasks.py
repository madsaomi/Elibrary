import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def auto_promote_classes():
    from apps.schools.services import auto_promote_classes as promote_service
    from apps.schools.models import School, Class

    today = timezone.now().date()

    current_year = f'{today.year - 1}-{today.year}'
    next_year = f'{today.year}-{today.year + 1}'

    schools = School.objects.all()
    promoted = 0
    for school in schools:
        if Class.objects.filter(school=school, academic_year=next_year).exists():
            continue
        promote_service(school, current_year, next_year)
        promoted += 1

    if promoted:
        logger.info(f'Auto-promoted classes in {promoted} schools: {current_year} -> {next_year}')
