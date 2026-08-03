import io

from minio import Minio

from app.config import settings

_client: Minio | None = None


def get_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
        if not _client.bucket_exists(settings.minio_bucket):
            _client.make_bucket(settings.minio_bucket)
    return _client


def upload_bytes(object_key: str, data: bytes, content_type: str) -> str:
    client = get_client()
    client.put_object(
        settings.minio_bucket, object_key, io.BytesIO(data), length=len(data), content_type=content_type
    )
    return object_key


def download_bytes(object_key: str) -> bytes:
    client = get_client()
    response = client.get_object(settings.minio_bucket, object_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()
