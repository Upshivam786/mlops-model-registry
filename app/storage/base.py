from abc import ABC, abstractmethod
from typing import BinaryIO, List, Optional
import os

class StorageBase(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def save(self, file_data: BinaryIO, path: str) -> str:
        """Save a file to storage.
        
        Args:
            file_data: File-like object containing the data to save
            path: Storage path where the file should be saved
            
        Returns:
            str: The actual path where the file was stored (may include backend-specific prefix)
        """
        pass

    @abstractmethod
    def load(self, path: str) -> BinaryIO:
        """Load a file from storage.
        
        Args:
            path: Storage path of the file to load
            
        Returns:
            BinaryIO: File-like object containing the file data
        """
        pass

    @abstractmethod
    def delete(self, path: str) -> bool:
        """Delete a file from storage.
        
        Args:
            path: Storage path of the file to delete
            
        Returns:
            bool: True if file was deleted, False if not found
        """
        pass

    @abstractmethod
    def list(self, prefix: str = "") -> List[str]:
        """List files in storage with optional prefix filter.
        
        Args:
            prefix: Optional prefix to filter results
            
        Returns:
            List[str]: List of file paths matching the prefix
        """
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        """Check if a file exists in storage.
        
        Args:
            path: Storage path to check
            
        Returns:
            bool: True if file exists, False otherwise
        """
        pass

    # ── Phase 5A ────────────────────────────────────────────────────────────
    def get_signed_url(self, path: str, expiration_seconds: int = 3600) -> Optional[str]:
        """Return a time-limited direct-download URL for a file, if the
        backend supports it.

        This is intentionally NOT an @abstractmethod. Backends that can't
        produce a signed URL (e.g. LocalStorage) simply inherit this default
        and return None — callers (the download route) must check for None
        and fall back to streaming the file through the API instead of
        raising an exception.

        Args:
            path: Storage path of the file
            expiration_seconds: How long the URL should remain valid

        Returns:
            Optional[str]: A signed URL, or None if unsupported / failed
        """
        return None
