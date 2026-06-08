from functools import lru_cache
import logging
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.storage.base import StorageBase
from app.storage.local import LocalStorage

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://user:password@localhost/modelregistry"
)

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db():
    """Dependency to get DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@lru_cache(maxsize=1)
def get_storage() -> StorageBase:
    """Return storage backend based on STORAGE_BACKEND."""

    storage_backend = os.getenv(
        "STORAGE_BACKEND",
        "local"
    ).lower()

    if storage_backend == "local":
        base_path = os.getenv(
            "STORAGE_BASE_PATH",
            "./model_artifacts"
        )

        logger.info(
            "Using local storage backend: %s",
            base_path
        )

        return LocalStorage(base_path=base_path)

    if storage_backend == "gcs":
        bucket_name = os.getenv("GCS_BUCKET")

        if not bucket_name:
            raise ValueError(
                "GCS_BUCKET environment variable must be set "
                "when STORAGE_BACKEND=gcs"
            )

        logger.info(
            "Using GCS storage backend: %s",
            bucket_name
        )

        from app.storage.gcs import GCSStorage

        return GCSStorage(bucket_name=bucket_name)

    raise ValueError(
        f"Unsupported storage backend: {storage_backend}. "
        "Supported values: local, gcs"
    )
