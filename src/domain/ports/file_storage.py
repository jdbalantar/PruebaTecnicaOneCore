"""Port: IFileStoragePort — abstract object-storage interface."""

from abc import ABC, abstractmethod


class IFileStoragePort(ABC):
    """Abstract port for binary file storage (e.g. Amazon S3).

    Implementations live in the infrastructure layer and are injected
    at application startup.
    """

    @abstractmethod
    def upload_file(
        self,
        file_bytes: bytes,
        key: str,
        bucket: str,
        content_type: str,
        metadata: dict,
    ) -> str:
        """Upload raw bytes to the storage backend and return the stored key.

        Args:
            file_bytes: Raw file content to store.
            key: Object key (path) under which the file will be stored.
            bucket: Target storage bucket name.
            content_type: MIME type of the file (e.g. ``"text/csv"``).
            metadata: Arbitrary string key-value pairs attached to the object.

        Returns:
            The ``key`` that was used to store the object.

        Raises:
            StorageError: If the upload operation fails.
        """
        ...

    @abstractmethod
    def get_presigned_url(self, key: str, bucket: str, expires_in: int = 3600) -> str:
        """Generate a time-limited pre-signed URL for a stored object.

        Args:
            key: Object key to generate the URL for.
            bucket: Bucket that holds the object.
            expires_in: URL validity in seconds (default 3600).

        Returns:
            A pre-signed HTTPS URL string.

        Raises:
            StorageError: If URL generation fails.
        """
        ...
