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