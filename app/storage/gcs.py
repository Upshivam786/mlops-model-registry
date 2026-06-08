import logging
import os
from io import BytesIO
from typing import BinaryIO, List, Optional

from google.cloud import storage

from app.storage.base import StorageBase

logger = logging.getLogger(__name__)


class GCSStorageError(Exception):
    """Raised when a GCS storage operation fails."""
    pass


class GCSStorage(StorageBase):
    """Google Cloud Storage implementation of StorageBase."""

    def __init__(self, bucket_name: Optional[str] = None):
        self.bucket_name = bucket_name or os.getenv("GCS_BUCKET")

        if not self.bucket_name:
            raise ValueError(
                "GCS_BUCKET environment variable must be configured"
            )

        self._client: Optional[storage.Client] = None
        self._bucket = None

        logger.info(
            "Initialized GCS storage backend for bucket: %s",
            self.bucket_name,
        )

    @property
    def client(self) -> storage.Client:
        if self._client is None:
            self._client = storage.Client()
        return self._client

    @property
    def bucket(self):
        if self._bucket is None:
            self._bucket = self.client.bucket(self.bucket_name)
        return self._bucket

    @staticmethod
    def _normalize_path(path: str) -> str:
        return path.lstrip("/")

    def save(self, file_data: BinaryIO, path: str) -> str:
        object_name = self._normalize_path(path)

        if hasattr(file_data, "seek"):
            file_data.seek(0)

        blob = self.bucket.blob(object_name)

        blob.upload_from_file(
            file_data,
            rewind=True,
            content_type="application/octet-stream",
        )

        logger.info("Uploaded artifact: %s", object_name)

        return path

    def load(self, path: str) -> BinaryIO:
        object_name = self._normalize_path(path)

        blob = self.bucket.blob(object_name)

        if not blob.exists():
            raise FileNotFoundError(path)

        buffer = BytesIO()

        blob.download_to_file(buffer)

        buffer.seek(0)

        logger.info("Downloaded artifact: %s", object_name)

        return buffer

    def delete(self, path: str) -> bool:
        object_name = self._normalize_path(path)

        blob = self.bucket.blob(object_name)

        if not blob.exists():
            return False

        blob.delete()

        logger.info("Deleted artifact: %s", object_name)

        return True

    def list(self, prefix: str = "") -> List[str]:
        object_prefix = self._normalize_path(prefix)

        blobs = self.bucket.list_blobs(prefix=object_prefix)

        return sorted([blob.name for blob in blobs])

    def exists(self, path: str) -> bool:
        object_name = self._normalize_path(path)

        return self.bucket.blob(object_name).exists()
