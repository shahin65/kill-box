"""Default Django file storage: Arvan Object Storage for user uploads.

STATIC files (CSS, JS, template images) stay on WhiteNoise / the local
STATIC_ROOT. Only FileField/ImageField and default_storage.save() go here.

S3 connection values come from Django settings (AWS_* in .env).
"""
from storages.backends.s3boto3 import S3Boto3Storage


class ArvanMediaStorage(S3Boto3Storage):
    """Public objects in the killbox-media Arvan bucket."""

    default_acl = 'public-read'
    file_overwrite = False
    querystring_auth = False
    object_parameters = {'CacheControl': 'public, max-age=31536000, immutable'}
