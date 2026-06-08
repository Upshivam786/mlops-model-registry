import io
import tempfile
import os
from fastapi.testclient import TestClient
from app.main import app
from app.models import Base
from app.dependencies import get_db, get_storage
from app.storage.local import LocalStorage
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest
import shutil

def create_test_client():
    """Create a fresh test client with isolated database and storage."""
    # Create temporary database for this test instance
    import tempfile
    db_fd, db_path = tempfile.mkstemp()
    SQLALCHEMY_TEST_DATABASE_URL = f"sqlite:///{db_path}"
    engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    def override_get_db():
        try:
            db = TestingSessionLocal()
            yield db
        finally:
            db.close()
    
    # Create a single storage instance for this test
    storage_tmpdir = tempfile.mkdtemp()
    storage_instance = LocalStorage(base_path=storage_tmpdir)
    
    def override_get_storage():
        return storage_instance
    
    # Create fresh app instance with overridden dependencies
    from app.main import app as original_app
    original_app.dependency_overrides[get_db] = override_get_db
    original_app.dependency_overrides[get_storage] = override_get_storage
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    client = TestClient(original_app)
    
    # Cleanup function
    def cleanup():
        original_app.dependency_overrides.clear()
        try:
            os.unlink(db_path)
        except:
            pass
        try:
            shutil.rmtree(storage_tmpdir, ignore_errors=True)
        except:
            pass
    
    return client, cleanup

def test_root_endpoint():
    """Test the root endpoint."""
    client, cleanup = create_test_client()
    try:
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "Model Registry API is running"}
    finally:
        cleanup()

def test_health_endpoint():
    """Test the health endpoint."""
    client, cleanup = create_test_client()
    try:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
    finally:
        cleanup()

def test_create_model():
    """Test creating a model."""
    client, cleanup = create_test_client()
    try:
        model_data = {
            "name": "test-model",
            "description": "A test model",
            "owner": "test-user",
            "tags": "test,ml"
        }
        response = client.post("/models/", json=model_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == model_data["name"]
        assert data["description"] == model_data["description"]
        assert data["id"] == 1
        assert "created_at" in data
        assert "updated_at" in data
    finally:
        cleanup()

def test_create_model_duplicate_name():
    """Test creating a model with duplicate name fails."""
    client, cleanup = create_test_client()
    try:
        model_data = {
            "name": "duplicate-test",
            "description": "First model",
        }
        response = client.post("/models/", json=model_data)
        assert response.status_code == 201
        
        # Try to create another model with same name
        model_data2 = {
            "name": "duplicate-test",
            "description": "Second model",
        }
        response = client.post("/models/", json=model_data2)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]
    finally:
        cleanup()

def test_get_models():
    """Test getting list of models."""
    client, cleanup = create_test_client()
    try:
        # Create a few models
        client.post("/models/", json={"name": "model-a"})
        client.post("/models/", json={"name": "model-b"})
        
        response = client.get("/models/")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["models"]) == 2
        assert data["page"] == 1
        assert data["size"] == 10
    finally:
        cleanup()

def test_get_model_by_id():
    """Test getting a specific model by ID."""
    client, cleanup = create_test_client()
    try:
        # Create a model
        model_data = {"name": "specific-model", "description": "To fetch"}
        response = client.post("/models/", json=model_data)
        model_id = response.json()["id"]
        
        # Get the model
        response = client.get(f"/models/{model_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == model_id
        assert data["name"] == model_data["name"]
        assert data["description"] == model_data["description"]
    finally:
        cleanup()

def test_get_model_not_found():
    """Test getting a non-existent model."""
    client, cleanup = create_test_client()
    try:
        response = client.get("/models/999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
    finally:
        cleanup()

def test_update_model():
    """Test updating a model."""
    client, cleanup = create_test_client()
    try:
        # Create a model
        model_data = {"name": "update-me", "description": "Original desc"}
        response = client.post("/models/", json=model_data)
        model_id = response.json()["id"]
        
        # Update the model
        update_data = {"description": "Updated description", "owner": "new-owner"}
        response = client.put(f"/models/{model_id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["description"] == update_data["description"]
        assert data["owner"] == update_data["owner"]
        assert data["name"] == model_data["name"]  # unchanged
    finally:
        cleanup()

def test_delete_model():
    """Test deleting a model."""
    client, cleanup = create_test_client()
    try:
        # Create a model
        model_data = {"name": "to-delete"}
        response = client.post("/models/", json=model_data)
        model_id = response.json()["id"]
        
        # Delete the model
        response = client.delete(f"/models/{model_id}")
        assert response.status_code == 204
        
        # Verify it's gone
        response = client.get(f"/models/{model_id}")
        assert response.status_code == 404
    finally:
        cleanup()

def test_create_model_version():
    """Test creating a model version."""
    client, cleanup = create_test_client()
    try:
        # Create a model first
        model_response = client.post("/models/", json={"name": "versioned-model"})
        model_id = model_response.json()["id"]
        
        # Create a version
        version_data = {
            "version": "1.0.0",
            "stage": "dev",
            "description": "Initial version"
        }
        response = client.post(f"/models/{model_id}/versions", json=version_data)
        assert response.status_code == 201
        data = response.json()
        assert data["version"] == version_data["version"]
        assert data["stage"] == version_data["stage"]
        assert data["model_id"] == model_id
        assert data["id"] == 1
    finally:
        cleanup()

def test_create_model_version_duplicate():
    """Test creating duplicate version fails."""
    client, cleanup = create_test_client()
    try:
        # Create model
        model_response = client.post("/models/", json={"name": "dup-version-model"})
        model_id = model_response.json()["id"]
        
        # Create first version
        version_data = {"version": "1.0.0", "stage": "dev"}
        client.post(f"/models/{model_id}/versions", json=version_data)
        
        # Try to create duplicate version
        response = client.post(f"/models/{model_id}/versions", json=version_data)
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]
    finally:
        cleanup()

def test_list_model_versions():
    """Test listing model versions."""
    client, cleanup = create_test_client()
    try:
        # Create model
        model_response = client.post("/models/", json={"name": "version-list-test"})
        model_id = model_response.json()["id"]
        
        # Create versions
        client.post(f"/models/{model_id}/versions", json={"version": "1.0.0", "stage": "dev"})
        client.post(f"/models/{model_id}/versions", json={"version": "2.0.0", "stage": "staging"})
        client.post(f"/models/{model_id}/versions", json={"version": "1.5.0", "stage": "dev"})
        
        # List all versions
        response = client.get(f"/models/{model_id}/versions")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["versions"]) == 3
        
        # List with stage filter
        response = client.get(f"/models/{model_id}/versions?stage=dev")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["versions"]) == 2
        for version in data["versions"]:
            assert version["stage"] == "dev"
    finally:
        cleanup()

def test_get_model_version():
    """Test getting a specific model version."""
    client, cleanup = create_test_client()
    try:
        # Create model and version
        model_response = client.post("/models/", json={"name": "get-version-test"})
        model_id = model_response.json()["id"]
        
        version_response = client.post(
            f"/models/{model_id}/versions", 
            json={"version": "3.2.1", "stage": "prod", "description": "Production version"}
        )
        version_id = version_response.json()["id"]
        
        # Get the version
        response = client.get(f"/models/{model_id}/versions/{version_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == version_id
        assert data["version"] == "3.2.1"
        assert data["stage"] == "prod"
        assert data["description"] == "Production version"
        assert data["model_id"] == model_id
    finally:
        cleanup()

def test_update_model_version():
    """Test updating a model version."""
    client, cleanup = create_test_client()
    try:
        # Create model and version
        model_response = client.post("/models/", json={"name": "update-version-test"})
        model_id = model_response.json()["id"]
        
        version_response = client.post(
            f"/models/{model_id}/versions",
            json={"version": "1.0.0", "stage": "dev"}
        )
        version_id = version_response.json()["id"]
        
        # Update the version
        update_data = {"stage": "prod", "description": "Now in production"}
        response = client.put(f"/models/{model_id}/versions/{version_id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["stage"] == update_data["stage"]
        assert data["description"] == update_data["description"]
        assert data["version"] == "1.0.0"  # unchanged
    finally:
        cleanup()

def test_delete_model_version():
    """Test deleting a model version."""
    client, cleanup = create_test_client()
    try:
        # Create model and version
        model_response = client.post("/models/", json={"name": "delete-version-test"})
        model_id = model_response.json()["id"]
        
        version_response = client.post(
            f"/models/{model_id}/versions",
            json={"version": "1.0.0", "stage": "dev"}
        )
        version_id = version_response.json()["id"]
        
        # Delete the version
        response = client.delete(f"/models/{model_id}/versions/{version_id}")
        assert response.status_code == 204
        
        # Verify it's gone
        response = client.get(f"/models/{model_id}/versions/{version_id}")
        assert response.status_code == 404
    finally:
        cleanup()

def test_upload_and_download_artifact():
    """Test uploading and downloading an artifact."""
    client, cleanup = create_test_client()
    try:
        # Create model and version
        model_response = client.post("/models/", json={"name": "artifact-test"})
        model_id = model_response.json()["id"]
        
        version_response = client.post(
            f"/models/{model_id}/versions",
            json={"version": "1.0.0", "stage": "dev"}
        )
        version_id = version_response.json()["id"]
        
        # Upload an artifact
        file_content = b"fake model weights data"
        files = {"file": ("model.pkl", io.BytesIO(file_content), "application/octet-stream")}
        data = {"artifact_type": "weights"}
        
        response = client.post(
            f"/models/{model_id}/versions/{version_id}/artifacts",
            files=files,
            data=data
        )
        assert response.status_code == 201
        artifact_data = response.json()
        assert artifact_data["artifact_type"] == "weights"
        assert artifact_data["version_id"] == version_id
        assert artifact_data["file_size"] == len(file_content)
        artifact_id = artifact_data["id"]
        
        # Download the artifact
        response = client.get(f"/models/{model_id}/versions/{version_id}/artifacts/{artifact_id}/download")
        assert response.status_code == 200
        assert response.content == file_content
        assert "attachment" in response.headers.get("content-disposition", "")
    finally:
        cleanup()

def test_list_model_artifacts():
    """Test listing model artifacts."""
    client, cleanup = create_test_client()
    try:
        # Create model and version
        model_response = client.post("/models/", json={"name": "artifact-list-test"})
        model_id = model_response.json()["id"]
        
        version_response = client.post(
            f"/models/{model_id}/versions",
            json={"version": "1.0.0", "stage": "dev"}
        )
        version_id = version_response.json()["id"]
        
        # Upload multiple artifacts
        client.post(
            f"/models/{model_id}/versions/{version_id}/artifacts",
            files={"file": ("config.json", io.BytesIO(b'{"lr": 0.01}'), "application/json")},
            data={"artifact_type": "config"}
        )
        client.post(
            f"/models/{model_id}/versions/{version_id}/artifacts",
            files={"file": ("metrics.json", io.BytesIO(b'{"acc": 0.95}'), "application/json")},
            data={"artifact_type": "metrics"}
        )
        client.post(
            f"/models/{model_id}/versions/{version_id}/artifacts",
            files={"file": ("model.pkl", io.BytesIO(b"weights"), "application/octet-stream")},
            data={"artifact_type": "weights"}
        )
        
        # List all artifacts
        response = client.get(f"/models/{model_id}/versions/{version_id}/artifacts")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["artifacts"]) == 3
        
        # List with artifact type filter
        response = client.get(f"/models/{model_id}/versions/{version_id}/artifacts?artifact_type=weights")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["artifacts"]) == 1
        assert data["artifacts"][0]["artifact_type"] == "weights"
    finally:
        cleanup()

def test_get_model_artifact():
    """Test getting a specific model artifact."""
    client, cleanup = create_test_client()
    try:
        # Create model and version
        model_response = client.post("/models/", json={"name": "get-artifact-test"})
        model_id = model_response.json()["id"]
        
        version_response = client.post(
            f"/models/{model_id}/versions",
            json={"version": "1.0.0", "stage": "dev"}
        )
        version_id = version_response.json()["id"]
        
        # Upload an artifact
        file_content = b"test artifact data"
        files = {"file": ("test.bin", io.BytesIO(file_content), "application/octet-stream")}
        data = {"artifact_type": "test"}
        
        upload_response = client.post(
            f"/models/{model_id}/versions/{version_id}/artifacts",
            files=files,
            data=data
        )
        assert upload_response.status_code == 201
        artifact_id = upload_response.json()["id"]
        
        # Get the artifact
        response = client.get(f"/models/{model_id}/versions/{version_id}/artifacts/{artifact_id}")
        assert response.status_code == 200
        artifact_data = response.json()
        assert artifact_data["id"] == artifact_id
        assert artifact_data["artifact_type"] == "test"
        assert artifact_data["version_id"] == version_id
    finally:
        cleanup()

def test_delete_model_artifact():
    """Test deleting a model artifact."""
    client, cleanup = create_test_client()
    try:
        # Create model and version
        model_response = client.post("/models/", json={"name": "delete-artifact-test"})
        model_id = model_response.json()["id"]
        
        version_response = client.post(
            f"/models/{model_id}/versions",
            json={"version": "1.0.0", "stage": "dev"}
        )
        version_id = version_response.json()["id"]
        
        # Upload an artifact
        files = {"file": ("todelete.bin", io.BytesIO(b"delete me"), "application/octet-stream")}
        data = {"artifact_type": "todelete"}
        
        upload_response = client.post(
            f"/models/{model_id}/versions/{version_id}/artifacts",
            files=files,
            data=data
        )
        assert upload_response.status_code == 201
        artifact_id = upload_response.json()["id"]
        
        # Delete the artifact
        response = client.delete(f"/models/{model_id}/versions/{version_id}/artifacts/{artifact_id}")
        assert response.status_code == 204
        
        # Verify it's gone
        response = client.get(f"/models/{model_id}/versions/{version_id}/artifacts/{artifact_id}")
        assert response.status_code == 404
    finally:
        cleanup()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])