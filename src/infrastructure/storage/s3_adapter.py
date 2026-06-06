"""AWS S3 implementation of IFileStoragePort."""

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from src.domain.exceptions import StorageError
from src.domain.ports.file_storage import IFileStoragePort


class S3FileStorageAdapter(IFileStoragePort):
    """AWS S3 implementation of IFileStoragePort.

    Wraps the boto3 S3 client and maps all botocore exceptions to the
    domain-level StorageError so callers remain decoupled from the AWS SDK.

    Args:
        settings: Application settings instance providing AWS credentials
            (``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``, ``AWS_REGION``).
    """

    def __init__(self, settings) -> None:
        """Initialise the S3 client from application settings.

        Args:
            settings: Populated Settings instance with AWS credentials.
        """
        self._s3 = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
            endpoint_url=settings.S3_ENDPOINT_URL,
            config=Config(s3={"addressing_style": "path"}),
        )
        self._region = settings.AWS_REGION

    def upload_file(
        self,
        file_bytes: bytes,
        key: str,
        bucket: str,
        content_type: str,
        metadata: dict,
    ) -> str:
        """Upload raw bytes to S3 and return the stored object key.

        Strips the ``x-amz-meta-`` prefix from metadata keys before passing
        them to S3, as boto3 adds it automatically.

        Args:
            file_bytes: The file content to upload.
            key: The S3 object key (path within the bucket).
            bucket: The S3 bucket name.
            content_type: MIME type of the file (e.g. ``"text/csv"``).
            metadata: Arbitrary string key-value pairs to attach to the object.

        Returns:
            The S3 key that was used to store the object.

        Raises:
            StorageError: If the upload operation fails for any reason.
        """
        try:
            self._s3.put_object(
                Bucket=bucket,
                Key=key,
                Body=file_bytes,
                ContentType=content_type,
                Metadata={
                    k.replace("x-amz-meta-", ""): v for k, v in metadata.items()
                },
            )
            return key
        except (ClientError, BotoCoreError) as exc:
            error_code = ""
            if isinstance(exc, ClientError):
                error_code = exc.response.get("Error", {}).get("Code", "")

            # In local environments (e.g., LocalStack), create bucket lazily and retry once.
            if error_code in {"NoSuchBucket", "404"}:
                self._ensure_bucket(bucket)
                try:
                    self._s3.put_object(
                        Bucket=bucket,
                        Key=key,
                        Body=file_bytes,
                        ContentType=content_type,
                        Metadata={
                            k.replace("x-amz-meta-", ""): v
                            for k, v in metadata.items()
                        },
                    )
                    return key
                except (ClientError, BotoCoreError) as retry_exc:
                    raise StorageError(
                        f"S3 upload failed for key '{key}' after bucket creation: {retry_exc}"
                    ) from retry_exc

            raise StorageError(f"S3 upload failed for key '{key}': {exc}") from exc

    def _ensure_bucket(self, bucket: str) -> None:
        """Create an S3 bucket if it does not already exist."""
        try:
            if self._region == "us-east-1":
                self._s3.create_bucket(Bucket=bucket)
            else:
                self._s3.create_bucket(
                    Bucket=bucket,
                    CreateBucketConfiguration={"LocationConstraint": self._region},
                )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
                return
            raise

    def get_presigned_url(
        self,
        key: str,
        bucket: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate a time-limited pre-signed URL for a stored S3 object.

        Args:
            key: The S3 object key to generate a URL for.
            bucket: The S3 bucket that holds the object.
            expires_in: URL validity period in seconds (default 3600).

        Returns:
            A pre-signed HTTPS URL string valid for ``expires_in`` seconds.

        Raises:
            StorageError: If URL generation fails for any reason.
        """
        try:
            return self._s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(
                f"Presigned URL generation failed for key '{key}': {exc}"
            ) from exc

    def health_check(self, bucket: str) -> tuple[bool, str]:
        """Verify S3 connectivity and bucket availability.

        Args:
            bucket: Bucket name expected by the application.

        Returns:
            Tuple ``(ok, detail)`` where ``ok`` indicates service availability.
        """
        try:
            self._s3.head_bucket(Bucket=bucket)
            return True, "bucket reachable"
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")

            if code in {"404", "NoSuchBucket", "NotFound"}:
                # Upload path already creates buckets lazily; treat as available.
                return True, "storage reachable (bucket missing; auto-create enabled)"

            return False, f"client error: {code or 'unknown'}"
        except BotoCoreError as exc:
            return False, f"boto error: {exc}"
