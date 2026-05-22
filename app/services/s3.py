# app/services/s3.py

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config
from functools import lru_cache

from app.core.config import get_settings

# Presigned URLs expire in 1 hour maximum (S3 enforces a 7-day hard limit,
# but we cap at 3600 seconds for security hygiene).
PRESIGNED_URL_EXPIRY = 3600


@lru_cache
def _get_client():
    """Return a singleton boto3 S3 client, constructed once per process."""
    settings = get_settings()
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
    )


def upload_fileobj(fileobj, s3_key: str, content_type: str) -> None:
    """
    Stream a file-like object directly to S3.

    Raises botocore.exceptions.ClientError on failure.
    The caller is responsible for rewinding the fileobj if needed.
    """
    settings = get_settings()
    _get_client().upload_fileobj(
        fileobj,
        settings.S3_BUCKET_NAME,
        s3_key,
        ExtraArgs={"ContentType": content_type},
    )


def generate_presigned_url(s3_key: str) -> str:
    """
    Generate a short-lived GET URL for a private S3 object.

    Expires in PRESIGNED_URL_EXPIRY seconds (1 hour).
    The file is never made public — all access goes through this URL.
    """
    settings = get_settings()
    return _get_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key},
        ExpiresIn=PRESIGNED_URL_EXPIRY,
    )


def generate_presigned_put_url(s3_key: str, content_type: str) -> str:
    """
    Generate a short-lived presigned PUT URL so a browser can upload directly to S3.

    Expires in PRESIGNED_URL_EXPIRY seconds (1 hour).
    The caller must PUT with a matching Content-Type header.
    """
    settings = get_settings()
    return _get_client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.S3_BUCKET_NAME,
            "Key": s3_key,
            "ContentType": content_type,
        },
        ExpiresIn=PRESIGNED_URL_EXPIRY,
    )


def delete_object(s3_key: str) -> None:
    """
    Delete an object from S3.

    S3 delete_object is idempotent — no error if the key doesn't exist.
    """
    settings = get_settings()
    _get_client().delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
