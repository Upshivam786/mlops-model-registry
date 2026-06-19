"""
tests/test_api.py

Full test suite with JWT auth and RBAC.
Uses SQLite in-memory DB and LocalStorage — no PostgreSQL or GCS needed.
Runs in GitHub Actions and locally.

Fixtures:
  client        — unauthenticated TestClient
  viewer_token  — token for role=viewer
  ml_token      — token for role=ml_engineer
  admin_token   — token for role=admin
"""

import io
import os
import shutil
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.dependencies import get_db, get_storage
from app.main import app
from app.models import Base
from app.storage.local import LocalStorage


# ── Test infrastructure ───────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def client():
    """
    Fresh TestClient per test function.
    Isolated SQLite DB + local storage temp dir.
    """
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    storage_dir = tempfile.mkdtemp()

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    storage_instance = LocalStorage(base_path=storage_dir)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    def override_get_storage():
        return storage_instance

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = override_get_storage

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    os.close(db_fd)
    os.unlink(db_path)
    shutil.rmtree(storage_dir, ignore_errors=True)


def register_and_login(client, username, password="testpass123"):
    """Register a user and return their JWT token."""
    client.post("/auth/register", json={
        "username": username,
        "email": f"{username}@test.com",
        "password": password,
    })
    resp = client.post("/auth/login", json={
        "username": username,
        "password": password,
    })
    return resp.json()["access_token"]


def promote(client, admin_token, username, role):
    """Promote a user to a given role using the admin endpoint."""
    # Get user list to find the user id
    resp = client.get("/admin/users", headers={"Authorization": f"Bearer {admin_token}"})
    users = resp.json()["users"]
    user = next(u for u in users if u["username"] == username)
    client.put(
        f"/admin/users/{user['id']}/role",
        json={"role": role},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # Re-login so the new role is baked into the returned token
    resp = client.post("/auth/login", json={"username": username, "password": "testpass123"})
    return resp.json()["access_token"]


@pytest.fixture(scope="function")
def tokens(client):
    """
    Returns dict with viewer, ml_engineer, and admin tokens.
    Sets up three users with correct roles.
    """
    # Register all three
    viewer_token  = register_and_login(client, "viewer_user")
    ml_token      = register_and_login(client, "ml_user")
    admin_token   = register_and_login(client, "admin_user")

    # Promote directly via DB override — admin_user promotes the others
    # First promote admin_user via psql-style direct ORM call
    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    from app.models import User
    db.query(User).filter(User.username == "admin_user").update({"role": "admin"})
    db.query(User).filter(User.username == "ml_user").update({"role": "ml_engineer"})
    db.commit()
    try:
        next(db_gen)
    except StopIteration:
        pass

    # Re-login to get fresh tokens with correct roles
    admin_token = register_and_login(client, "admin_user2")
    db_gen2 = app.dependency_overrides[get_db]()
    db2 = next(db_gen2)
    db2.query(User).filter(User.username == "admin_user2").update({"role": "admin"})
    db2.commit()
    try:
        next(db_gen2)
    except StopIteration:
        pass

    ml_token   = client.post("/auth/login", json={"username": "ml_user",     "password": "testpass123"}).json()["access_token"]
    admin_token = client.post("/auth/login", json={"username": "admin_user2", "password": "testpass123"}).json()["access_token"]
    viewer_token = client.post("/auth/login", json={"username": "viewer_user", "password": "testpass123"}).json()["access_token"]

    return {
        "viewer":  viewer_token,
        "ml":      ml_token,
        "admin":   admin_token,
    }


# ── Health endpoints ──────────────────────────────────────────────────────────

def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json() == {"message": "Model Registry API is running"}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "healthy"}


# ── Auth endpoints ─────────────────────────────────────────────────────────────

def test_register(client):
    r = client.post("/auth/register", json={
        "username": "newuser", "email": "new@test.com", "password": "pass123"
    })
    assert r.status_code == 200
    assert r.json()["username"] == "newuser"
    assert r.json()["role"] == "viewer"


def test_register_duplicate(client):
    client.post("/auth/register", json={"username": "dup", "email": "dup@test.com", "password": "pass"})
    r = client.post("/auth/register", json={"username": "dup", "email": "dup2@test.com", "password": "pass"})
    assert r.status_code == 400


def test_login(client):
    client.post("/auth/register", json={"username": "logintest", "email": "l@test.com", "password": "pass"})
    r = client.post("/auth/login", json={"username": "logintest", "password": "pass"})
    assert r.status_code == 200
    assert "access_token" in r.json()
    assert r.json()["token_type"] == "bearer"


def test_login_wrong_password(client):
    client.post("/auth/register", json={"username": "logintest2", "email": "l2@test.com", "password": "correct"})
    r = client.post("/auth/login", json={"username": "logintest2", "password": "wrong"})
    assert r.status_code == 401


# ── RBAC — unauthenticated ────────────────────────────────────────────────────

def test_no_token_blocked(client):
    r = client.get("/models")
    assert r.status_code == 401


# ── RBAC — viewer ────────────────────────────────────────────────────────────

def test_viewer_can_read(client, tokens):
    r = client.get("/models", headers={"Authorization": f"Bearer {tokens['viewer']}"})
    assert r.status_code == 200


def test_viewer_cannot_create(client, tokens):
    r = client.post("/models",
        json={"name": "viewer-model"},
        headers={"Authorization": f"Bearer {tokens['viewer']}"},
    )
    assert r.status_code == 403


def test_viewer_cannot_delete(client, tokens):
    # ml creates a model first
    client.post("/models",
        json={"name": "to-delete"},
        headers={"Authorization": f"Bearer {tokens['ml']}"},
    )
    r = client.delete("/models/1", headers={"Authorization": f"Bearer {tokens['viewer']}"})
    assert r.status_code == 403


# ── RBAC — ml_engineer ───────────────────────────────────────────────────────

def test_ml_can_create_model(client, tokens):
    r = client.post("/models",
        json={"name": "ml-model", "description": "test"},
        headers={"Authorization": f"Bearer {tokens['ml']}"},
    )
    assert r.status_code == 201
    assert r.json()["name"] == "ml-model"


def test_ml_cannot_delete(client, tokens):
    client.post("/models",
        json={"name": "ml-nodelete"},
        headers={"Authorization": f"Bearer {tokens['ml']}"},
    )
    r = client.delete("/models/1", headers={"Authorization": f"Bearer {tokens['ml']}"})
    assert r.status_code == 403


# ── RBAC — admin ─────────────────────────────────────────────────────────────

def test_admin_can_delete(client, tokens):
    client.post("/models",
        json={"name": "admin-delete-test"},
        headers={"Authorization": f"Bearer {tokens['ml']}"},
    )
    r = client.delete("/models/1", headers={"Authorization": f"Bearer {tokens['admin']}"})
    assert r.status_code == 204


def test_admin_can_read_audit_log(client, tokens):
    r = client.get("/audit-logs", headers={"Authorization": f"Bearer {tokens['admin']}"})
    assert r.status_code == 200


def test_viewer_cannot_read_audit_log(client, tokens):
    r = client.get("/audit-logs", headers={"Authorization": f"Bearer {tokens['viewer']}"})
    assert r.status_code == 403


def test_ml_cannot_read_audit_log(client, tokens):
    r = client.get("/audit-logs", headers={"Authorization": f"Bearer {tokens['ml']}"})
    assert r.status_code == 403


# ── Models CRUD ───────────────────────────────────────────────────────────────

def test_create_model(client, tokens):
    r = client.post("/models",
        json={"name": "crud-model", "description": "desc", "owner": "shivam", "tags": "a,b"},
        headers={"Authorization": f"Bearer {tokens['ml']}"},
    )
    assert r.status_code == 201
    d = r.json()
    assert d["name"] == "crud-model"
    assert d["owner"] == "shivam"
    assert "id" in d


def test_create_model_duplicate(client, tokens):
    h = {"Authorization": f"Bearer {tokens['ml']}"}
    client.post("/models", json={"name": "dup-model"}, headers=h)
    r = client.post("/models", json={"name": "dup-model"}, headers=h)
    assert r.status_code == 400
    assert "already exists" in r.json()["detail"]


def test_list_models(client, tokens):
    h = {"Authorization": f"Bearer {tokens['ml']}"}
    client.post("/models", json={"name": "list-a"}, headers=h)
    client.post("/models", json={"name": "list-b"}, headers=h)
    r = client.get("/models", headers={"Authorization": f"Bearer {tokens['viewer']}"})
    assert r.status_code == 200
    assert r.json()["total"] >= 2


def test_get_model_not_found(client, tokens):
    r = client.get("/models/999", headers={"Authorization": f"Bearer {tokens['viewer']}"})
    assert r.status_code == 404


def test_update_model(client, tokens):
    h_ml = {"Authorization": f"Bearer {tokens['ml']}"}
    create_r = client.post("/models", json={"name": "update-model"}, headers=h_ml)
    mid = create_r.json()["id"]
    r = client.put(f"/models/{mid}",
        json={"description": "updated", "owner": "new-owner"},
        headers=h_ml,
    )
    assert r.status_code == 200
    assert r.json()["description"] == "updated"


def test_delete_model(client, tokens):
    h_ml    = {"Authorization": f"Bearer {tokens['ml']}"}
    h_admin = {"Authorization": f"Bearer {tokens['admin']}"}
    create_r = client.post("/models", json={"name": "del-model"}, headers=h_ml)
    mid = create_r.json()["id"]
    r = client.delete(f"/models/{mid}", headers=h_admin)
    assert r.status_code == 204
    r = client.get(f"/models/{mid}", headers=h_ml)
    assert r.status_code == 404


# ── Versions ──────────────────────────────────────────────────────────────────

def test_create_version(client, tokens):
    h = {"Authorization": f"Bearer {tokens['ml']}"}
    mid = client.post("/models", json={"name": "ver-model"}, headers=h).json()["id"]
    r = client.post(f"/models/{mid}/versions",
        json={"version": "1.0.0", "stage": "dev", "description": "first"},
        headers=h,
    )
    assert r.status_code == 201
    assert r.json()["version"] == "1.0.0"
    assert r.json()["stage"] == "dev"


def test_duplicate_version(client, tokens):
    h = {"Authorization": f"Bearer {tokens['ml']}"}
    mid = client.post("/models", json={"name": "dup-ver"}, headers=h).json()["id"]
    client.post(f"/models/{mid}/versions", json={"version": "1.0.0"}, headers=h)
    r = client.post(f"/models/{mid}/versions", json={"version": "1.0.0"}, headers=h)
    assert r.status_code == 400


def test_promote_version(client, tokens):
    h = {"Authorization": f"Bearer {tokens['ml']}"}
    mid = client.post("/models", json={"name": "promote-model"}, headers=h).json()["id"]
    vid = client.post(f"/models/{mid}/versions", json={"version": "1.0.0", "stage": "dev"}, headers=h).json()["id"]
    r = client.put(f"/models/{mid}/versions/{vid}",
        json={"stage": "prod"},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["stage"] == "prod"


def test_compare_versions(client, tokens):
    h = {"Authorization": f"Bearer {tokens['ml']}"}
    mid = client.post("/models", json={"name": "compare-model"}, headers=h).json()["id"]
    client.post(f"/models/{mid}/versions", json={"version": "1.0.0", "stage": "dev"}, headers=h)
    client.post(f"/models/{mid}/versions", json={"version": "2.0.0", "stage": "staging"}, headers=h)
    r = client.get(f"/models/{mid}/versions/compare",
        headers={"Authorization": f"Bearer {tokens['viewer']}"},
    )
    assert r.status_code == 200
    assert r.json()["total"] == 2


# ── Artifacts ─────────────────────────────────────────────────────────────────

def test_upload_download_artifact(client, tokens):
    h = {"Authorization": f"Bearer {tokens['ml']}"}
    mid = client.post("/models", json={"name": "artifact-model"}, headers=h).json()["id"]
    vid = client.post(f"/models/{mid}/versions", json={"version": "1.0.0"}, headers=h).json()["id"]

    file_bytes = b"fake model weights"
    r = client.post(
        f"/models/{mid}/versions/{vid}/artifacts",
        files={"file": ("model.pkl", io.BytesIO(file_bytes), "application/octet-stream")},
        data={"artifact_type": "weights"},
        headers=h,
    )
    assert r.status_code == 201
    aid = r.json()["id"]

    r = client.get(
        f"/models/{mid}/versions/{vid}/artifacts/{aid}/download",
        headers={"Authorization": f"Bearer {tokens['viewer']}"},
    )
    assert r.status_code == 200
    assert r.content == file_bytes


def test_delete_artifact(client, tokens):
    h_ml    = {"Authorization": f"Bearer {tokens['ml']}"}
    h_admin = {"Authorization": f"Bearer {tokens['admin']}"}
    mid = client.post("/models", json={"name": "del-art-model"}, headers=h_ml).json()["id"]
    vid = client.post(f"/models/{mid}/versions", json={"version": "1.0.0"}, headers=h_ml).json()["id"]
    aid = client.post(
        f"/models/{mid}/versions/{vid}/artifacts",
        files={"file": ("f.bin", io.BytesIO(b"data"), "application/octet-stream")},
        data={"artifact_type": "weights"},
        headers=h_ml,
    ).json()["id"]
    r = client.delete(f"/models/{mid}/versions/{vid}/artifacts/{aid}", headers=h_admin)
    assert r.status_code == 204


# ── Experiment tracking ───────────────────────────────────────────────────────

def test_log_and_get_training_run(client, tokens):
    h = {"Authorization": f"Bearer {tokens['ml']}"}
    mid = client.post("/models", json={"name": "exp-model"}, headers=h).json()["id"]
    vid = client.post(f"/models/{mid}/versions", json={"version": "1.0.0"}, headers=h).json()["id"]

    r = client.post(
        f"/models/{mid}/versions/{vid}/training-run",
        json={
            "dataset_name": "test-dataset",
            "accuracy": 0.94,
            "f1_score": 0.91,
            "loss": 0.12,
            "framework": "pytorch",
            "training_duration": 3600,
        },
        headers=h,
    )
    assert r.status_code == 201
    assert r.json()["accuracy"] == 0.94

    r = client.get(
        f"/models/{mid}/versions/{vid}/training-run",
        headers={"Authorization": f"Bearer {tokens['viewer']}"},
    )
    assert r.status_code == 200
    assert r.json()["f1_score"] == 0.91


def test_experiments_filter(client, tokens):
    h = {"Authorization": f"Bearer {tokens['ml']}"}
    mid = client.post("/models", json={"name": "filter-model"}, headers=h).json()["id"]
    vid = client.post(f"/models/{mid}/versions", json={"version": "1.0.0", "stage": "prod"}, headers=h).json()["id"]
    client.post(
        f"/models/{mid}/versions/{vid}/training-run",
        json={"accuracy": 0.95, "f1_score": 0.92, "framework": "sklearn"},
        headers=h,
    )

    r = client.get("/experiments?min_accuracy=0.90",
        headers={"Authorization": f"Bearer {tokens['viewer']}"},
    )
    assert r.status_code == 200
    assert r.json()["total"] >= 1

    r = client.get("/experiments?min_accuracy=0.99",
        headers={"Authorization": f"Bearer {tokens['viewer']}"},
    )
    assert r.status_code == 200
    assert r.json()["total"] == 0


# ── Audit log ────────────────────────────────────────────────────────────────

def test_audit_log_records_create(client, tokens):
    h_ml    = {"Authorization": f"Bearer {tokens['ml']}"}
    h_admin = {"Authorization": f"Bearer {tokens['admin']}"}
    client.post("/models", json={"name": "audit-model"}, headers=h_ml)
    r = client.get("/audit-logs", headers=h_admin)
    assert r.status_code == 200
    actions = [log["action"] for log in r.json()["logs"]]
    assert "CREATE" in actions


def test_audit_log_records_promote(client, tokens):
    h_ml    = {"Authorization": f"Bearer {tokens['ml']}"}
    h_admin = {"Authorization": f"Bearer {tokens['admin']}"}
    mid = client.post("/models", json={"name": "promote-audit"}, headers=h_ml).json()["id"]
    vid = client.post(f"/models/{mid}/versions", json={"version": "1.0.0", "stage": "dev"}, headers=h_ml).json()["id"]
    client.put(f"/models/{mid}/versions/{vid}", json={"stage": "prod"}, headers=h_ml)
    r = client.get("/audit-logs?action=PROMOTE", headers=h_admin)
    assert r.status_code == 200
    assert r.json()["total"] >= 1


# ── Admin role management ────────────────────────────────────────────────────

def test_admin_list_users(client, tokens):
    r = client.get("/admin/users", headers={"Authorization": f"Bearer {tokens['admin']}"})
    assert r.status_code == 200
    assert "users" in r.json()


def test_viewer_cannot_list_users(client, tokens):
    r = client.get("/admin/users", headers={"Authorization": f"Bearer {tokens['viewer']}"})
    assert r.status_code == 403


def test_admin_promote_user(client, tokens):
    h_admin = {"Authorization": f"Bearer {tokens['admin']}"}
    # register a new user
    client.post("/auth/register", json={"username": "promoteme", "email": "p@t.com", "password": "pass"})
    # find their id
    users = client.get("/admin/users", headers=h_admin).json()["users"]
    uid = next(u["id"] for u in users if u["username"] == "promoteme")
    # promote
    r = client.put(f"/admin/users/{uid}/role", json={"role": "ml_engineer"}, headers=h_admin)
    assert r.status_code == 200
    assert r.json()["role"] == "ml_engineer"


def test_admin_deactivate_user(client, tokens):
    h_admin = {"Authorization": f"Bearer {tokens['admin']}"}
    client.post("/auth/register", json={"username": "deactivateme", "email": "d@t.com", "password": "pass"})
    users = client.get("/admin/users", headers=h_admin).json()["users"]
    uid = next(u["id"] for u in users if u["username"] == "deactivateme")
    r = client.delete(f"/admin/users/{uid}", headers=h_admin)
    assert r.status_code == 200
    assert r.json()["is_active"] == False


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
