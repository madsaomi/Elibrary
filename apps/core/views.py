from django.http import JsonResponse
from django.db import connection
import redis


def healthcheck(request):
    checks = {}

    # Database
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        checks['database'] = 'ok'
    except Exception as e:
        checks['database'] = f'error: {str(e)}'

    # Redis
    try:
        from django.conf import settings
        r = redis.from_url(settings.CELERY_BROKER_URL)
        r.ping()
        checks['redis'] = 'ok'
    except Exception as e:
        checks['redis'] = f'error: {str(e)}'

    status = all(v == 'ok' for v in checks.values())
    return JsonResponse({'status': 'healthy' if status else 'degraded', 'checks': checks}, status=200 if status else 503)
