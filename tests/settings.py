from config.settings import *  # noqa: F401,F403

# Override staticfiles storage for tests (no collectstatic needed)
STORAGES['staticfiles']['BACKEND'] = 'django.contrib.staticfiles.storage.StaticFilesStorage'
