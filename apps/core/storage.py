from pathlib import Path
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from storages.backends.s3boto3 import S3Boto3Storage


def get_cover_storage():
    if settings.USE_S3:
        return S3Boto3Storage(
            bucket_name=settings.AWS_STORAGE_BUCKET_NAME,
            location='covers',
            default_acl='public-read',
            file_overwrite=False,
        )
    media_root = Path(settings.MEDIA_ROOT) if isinstance(settings.MEDIA_ROOT, str) else settings.MEDIA_ROOT
    return FileSystemStorage(location=media_root / 'covers')
