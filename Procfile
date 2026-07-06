web: daphne config.asgi:application --port $PORT --bind 0.0.0.0
worker: celery -A config worker --loglevel=info
beat: celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
