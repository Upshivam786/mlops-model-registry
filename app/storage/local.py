import os
import shutil
from typing import BinaryIO, List
from .base import StorageBase

class LocalStorage(StorageBase):
    """Local filesystem storage implementation."""

    def __init__(self, base_path: str = "./model_artifacts"):
        """Initialize local storage.
        
        Args:
            base_path: Root directory where artifacts will be stored
        """
        self.base_path = os.path.abspath(base_path)
        # Ensure base directory exists
        os.makedirs(self.base_path, exist_ok=True)

    def _get_full_path(self, path: str) -> str:
        """Convert storage path to full filesystem path."""
        # Normalize path and join with base
        normalized_path = path.lstrip('/')
        full_path = os.path.join(self.base_path, normalized_path)
        # Ensure the directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        return full_path

    def save(self, file_data: BinaryIO, path: str) -> str:
        """Save a file to local filesystem."""
        full_path = self._get_full_path(path)
        # Ensure directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Copy file data to destination
        with open(full_path, 'wb') as f:
            if hasattr(file_data, 'seek'):
                file_data.seek(0)
            shutil.copyfileobj(file_data, f)
        
        return path

    def load(self, path: str) -> BinaryIO:
        """Load a file from local filesystem."""
        full_path = self._get_full_path(path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {path}")
        return open(full_path, 'rb')

    def delete(self, path: str) -> bool:
        """Delete a file from local filesystem."""
        full_path = self._get_full_path(path)
        if os.path.exists(full_path):
            os.remove(full_path)
            # Try to remove parent directories if they're empty
            try:
                os.removedirs(os.path.dirname(full_path))
            except OSError:
                pass  # Directory not empty, that's fine
            return True
        return False

    def list(self, prefix: str = "") -> List[str]:
        """List files in local filesystem with optional prefix."""
        # Ensure prefix ends with separator if not empty
        if prefix and not prefix.endswith('/'):
            search_prefix = prefix + '/'
        else:
            search_prefix = prefix
        
        search_dir = os.path.join(self.base_path, search_prefix.lstrip('/'))
        if not os.path.exists(search_dir):
            return []
        
        results = []
        for root, dirs, files in os.walk(search_dir):
            for file in files:
                full_path = os.path.join(root, file)
                # Convert to relative path from base_path
                rel_path = os.path.relpath(full_path, self.base_path)
                # Apply prefix filter
                if prefix:
                    if rel_path.startswith(prefix):
                        results.append(rel_path)
                else:
                    results.append(rel_path)
        
        return sorted(results)

    def exists(self, path: str) -> bool:
        """Check if a file exists in local filesystem."""
        full_path = self._get_full_path(path)
        return os.path.isfile(full_path)