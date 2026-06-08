import io
import tempfile
import os
from app.storage.local import LocalStorage
from app.storage.base import StorageBase

def test_storage_base_is_abstract():
    """Test that StorageBase cannot be instantiated directly."""
    try:
        StorageBase()
        assert False, "Should not be able to instantiate abstract base class"
    except TypeError:
        pass  # Expected

def test_local_storage_initialization():
    """Test that LocalStorage initializes correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(base_path=tmpdir)
        assert storage.base_path == os.path.abspath(tmpdir)
        assert os.path.exists(storage.base_path)

def test_local_storage_save_and_load():
    """Test saving and loading a file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(base_path=tmpdir)
        test_data = b"Hello, World!"
        file_obj = io.BytesIO(test_data)
        
        # Save file
        path = "test/file.txt"
        saved_path = storage.save(file_obj, path)
        assert saved_path == path
        
        # Load file
        loaded_obj = storage.load(path)
        assert loaded_obj.read() == test_data
        loaded_obj.close()

def test_local_storage_save_overwrite():
    """Test that saving overwrites existing file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(base_path=tmpdir)
        
        # Save first version
        file1 = io.BytesIO(b"Version 1")
        storage.save(file1, "test.txt")
        
        # Save second version
        file2 = io.BytesIO(b"Version 2")
        storage.save(file2, "test.txt")
        
        # Load and verify it's the second version
        loaded = storage.load("test.txt")
        assert loaded.read() == b"Version 2"
        loaded.close()

def test_local_storage_delete():
    """Test deleting a file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(base_path=tmpdir)
        
        # Save a file
        file_obj = io.BytesIO(b"to be deleted")
        storage.save(file_obj, "to_delete.txt")
        
        # Verify it exists
        assert storage.exists("to_delete.txt")
        
        # Delete it
        result = storage.delete("to_delete.txt")
        assert result is True
        
        # Verify it's gone
        assert not storage.exists("to_delete.txt")
        
        # Try deleting again (should return False)
        result = storage.delete("to_delete.txt")
        assert result is False

def test_local_storage_list():
    """Test listing files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(base_path=tmpdir)
        
        # Create some test files
        storage.save(io.BytesIO(b"file1"), "dir/file1.txt")
        storage.save(io.BytesIO(b"file2"), "dir/subdir/file2.txt")
        storage.save(io.BytesIO(b"file3"), "other.txt")
        
        # List all files
        all_files = storage.list()
        assert "dir/file1.txt" in all_files
        assert "dir/subdir/file2.txt" in all_files
        assert "other.txt" in all_files
        assert len(all_files) == 3
        
        # List with prefix
        dir_files = storage.list("dir")
        assert "dir/file1.txt" in dir_files
        assert "dir/subdir/file2.txt" in dir_files
        assert "other.txt" not in dir_files
        assert len(dir_files) == 2
        
        # List with subdir prefix
        subdir_files = storage.list("dir/subdir")
        assert "dir/subdir/file2.txt" in subdir_files
        assert len(subdir_files) == 1

def test_local_storage_exists():
    """Test exists method."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = LocalStorage(base_path=tmpdir)
        
        # Non-existent file
        assert not storage.exists("nonexistent.txt")
        
        # Create file
        storage.save(io.BytesIO(b"test"), "exists.txt")
        
        # Now exists
        assert storage.exists("exists.txt")
        
        # Delete and check again
        storage.delete("exists.txt")
        assert not storage.exists("exists.txt")

if __name__ == "__main__":
    test_storage_base_is_abstract()
    test_local_storage_initialization()
    test_local_storage_save_and_load()
    test_local_storage_save_overwrite()
    test_local_storage_delete()
    test_local_storage_list()
    test_local_storage_exists()
    print("All tests passed!")