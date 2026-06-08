from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.storage.local import LocalStorage
from app.storage.base import StorageBase
import os

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/modelregistry")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Dependency to get DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Storage setup
STORAGE_BASE_PATH = os.getenv("STORAGE_BASE_PATH", "./model_artifacts")
storage_instance = LocalStorage(base_path=STORAGE_BASE_PATH)

def get_storage() -> StorageBase:
    """Dependency to get storage instance."""
    return storage_instance