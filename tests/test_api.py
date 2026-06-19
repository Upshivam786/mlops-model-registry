"""
tests/test_api.py

Full test suite with JWT auth and RBAC.
Uses SQLite in-memory DB and LocalStorage — no PostgreSQL or GCS needed.

Strategy for roles:
- Register users normally (all start as viewer)
- Promote via PUT /admin/users/{id}/role using a pre-promoted admin
- Admin is promoted by directly calling the ORM through the dependency override
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
from app.models import Base, User
from app.storage.local import LocalStorage


# ── Fixture: isolated client per test ────────────────────────────────────────

@pytest.fixture(scope="function")
def client():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    storage_dir    = tempfile.mkdtemp()

    engine         = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    SessionLocal   = sessionmaker(autocommit=False, autoflush=False, bind=engine)
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

    app.dependency_overrides[get_db]      = override_get_db
    app.dependency_overrides[get_storage] = override_get_storage

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    os.close(db_fd)
    os.unlink(db_path)
    shutil.rmtree(storage_dir, ignore_errors=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def register(client, username, password="Pass1234"):
    return client.post("/auth/register", json={
        "username": username,
        "email":    f"{username}@test.com",
        "password": password,
    })


def login(client, username, password="Pass1234"):
    resp = client.post("/auth/login", json={"username": username, "password": password})
    return resp.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def promote_via_db(client, username, role):
    """
    Directly update the role in the test DB via the dependency override.
    Returns a fresh token with the new role baked in.
    """
    db_gen = app.dependency_overrides[get_db]()
    db     = next(db_gen)
    db.query(User).filter(User.username == username).update({"role": role})
    db.commit()
    try:
        next(db_gen)
    except StopIteration:
        pass
    # Re-login to get token with new role
    resp = client.post("/auth/login", json={"username": username, "password": "Pass1234"})
    return resp.json()["access_token"]


@pytest.fixture(scope="function")
def tokens(client):
    """viewer, ml_engineer, and admin tokens."""
    register(client, "viewer_user")
    register(client, "ml_user")
    register(client, "admin_user")

    viewer_token = login(client, "viewer_user")
    ml_token     = promote_via_db(client, "ml_user",    "ml_engineer")
    admin_token  = promote_via_db(client, "admin_user", "admin")

    return {"viewer": viewer_token, "ml": ml_token, "admin": admin_token}


# ── Health ────────────────────────────────────────────────────────────────────

def test_root(client):
    assert client.get("/").status_code == 200

def test_health(client):
    assert client.get("/health").status_code == 200


# ── Auth ──────────────────────────────────────────────────────────────────────

def test_register(client):
    r = register(client, "newuser")
    assert r.status_code == 200
    assert r.json()["role"] == "viewer"

def test_register_duplicate(client):
    register(client, "dup")
    assert register(client, "dup").status_code == 400

def test_login_success(client):
    register(client, "logintest")
    r = client.post("/auth/login", json={"username": "logintest", "password": "Pass1234"})
    assert r.status_code == 200
    assert "access_token" in r.json()

def test_login_wrong_password(client):
    register(client, "wrongpass")
    r = client.post("/auth/login", json={"username": "wrongpass", "password": "badpass"})
    assert r.status_code == 401

def test_refresh_token(client):
    register(client, "refreshtest")
    r = client.post("/auth/login", json={"username": "refreshtest", "password": "Pass1234"})
    refresh = r.json().get("refresh_token")
    assert refresh is not None
    r2 = client.post(f"/auth/refresh?refresh_token={refresh}")
    assert r2.status_code == 200
    assert "access_token" in r2.json()


# ── RBAC: unauthenticated ─────────────────────────────────────────────────────

def test_no_token_blocked(client):
    assert client.get("/models").status_code == 401


# ── RBAC: viewer ──────────────────────────────────────────────────────────────

def test_viewer_can_read(client, tokens):
    assert client.get("/models", headers=auth(tokens["viewer"])).status_code == 200

def test_viewer_cannot_create(client, tokens):
    r = client.post("/models", json={"name": "v"}, headers=auth(tokens["viewer"]))
    assert r.status_code == 403

def test_viewer_cannot_delete(client, tokens):
    client.post("/models", json={"name": "nodelete"}, headers=auth(tokens["ml"]))
    assert client.delete("/models/1", headers=auth(tokens["viewer"])).status_code == 403

def test_viewer_cannot_read_audit_log(client, tokens):
    assert client.get("/audit-logs", headers=auth(tokens["viewer"])).status_code == 403

def test_viewer_cannot_list_users(client, tokens):
    assert client.get("/admin/users", headers=auth(tokens["viewer"])).status_code == 403


# ── RBAC: ml_engineer ─────────────────────────────────────────────────────────

def test_ml_can_create_model(client, tokens):
    r = client.post("/models", json={"name": "ml-model"}, headers=auth(tokens["ml"]))
    assert r.status_code == 201

def test_ml_cannot_delete(client, tokens):
    client.post("/models", json={"name": "ml-nd"}, headers=auth(tokens["ml"]))
    assert client.delete("/models/1", headers=auth(tokens["ml"])).status_code == 403

def test_ml_cannot_read_audit_log(client, tokens):
    assert client.get("/audit-logs", headers=auth(tokens["ml"])).status_code == 403


# ── RBAC: admin ───────────────────────────────────────────────────────────────

def test_admin_can_delete(client, tokens):
    client.post("/models", json={"name": "del-test"}, headers=auth(tokens["ml"]))
    assert client.delete("/models/1", headers=auth(tokens["admin"])).status_code == 204

def test_admin_can_read_audit_log(client, tokens):
    assert client.get("/audit-logs", headers=auth(tokens["admin"])).status_code == 200


# ── Models CRUD ───────────────────────────────────────────────────────────────

def test_create_model(client, tokens):
    r = client.post("/models",
        json={"name": "mymodel", "description": "d", "owner": "shivam"},
        headers=auth(tokens["ml"]),
    )
    assert r.status_code == 201
    assert r.json()["name"] == "mymodel"

def test_create_model_duplicate(client, tokens):
    h = auth(tokens["ml"])
    client.post("/models", json={"name": "dup"}, headers=h)
    assert client.post("/models", json={"name": "dup"}, headers=h).status_code == 400

def test_list_models(client, tokens):
    h = auth(tokens["ml"])
    client.post("/models", json={"name": "a"}, headers=h)
    client.post("/models", json={"name": "b"}, headers=h)
    r = client.get("/models", headers=auth(tokens["viewer"]))
    assert r.status_code == 200
    assert r.json()["total"] >= 2

def test_get_model_not_found(client, tokens):
    r = client.get("/models/999", headers=auth(tokens["viewer"]))
    assert r.status_code == 404

def test_update_model(client, tokens):
    mid = client.post("/models", json={"name": "upd"}, headers=auth(tokens["ml"])).json()["id"]
    r   = client.put(f"/models/{mid}", json={"description": "new"}, headers=auth(tokens["ml"]))
    assert r.status_code == 200
    assert r.json()["description"] == "new"

def test_delete_model(client, tokens):
    mid = client.post("/models", json={"name": "del"}, headers=auth(tokens["ml"])).json()["id"]
    assert client.delete(f"/models/{mid}", headers=auth(tokens["admin"])).status_code == 204
    assert client.get(f"/models/{mid}", headers=auth(tokens["viewer"])).status_code == 404


# ── Versions ──────────────────────────────────────────────────────────────────

def test_create_version(client, tokens):
    mid = client.post("/models", json={"name": "vm"}, headers=auth(tokens["ml"])).json()["id"]
    r   = client.post(f"/models/{mid}/versions",
        json={"version": "1.0.0", "stage": "dev"},
        headers=auth(tokens["ml"]),
    )
    assert r.status_code == 201
    assert r.json()["stage"] == "dev"

def test_duplicate_version(client, tokens):
    h   = auth(tokens["ml"])
    mid = client.post("/models", json={"name": "dvm"}, headers=h).json()["id"]
    client.post(f"/models/{mid}/versions", json={"version": "1.0.0"}, headers=h)
    assert client.post(f"/models/{mid}/versions", json={"version": "1.0.0"}, headers=h).status_code == 400

def test_promote_version(client, tokens):
    h   = auth(tokens["ml"])
    mid = client.post("/models", json={"name": "prom"}, headers=h).json()["id"]
    vid = client.post(f"/models/{mid}/versions", json={"version": "1.0.0", "stage": "dev"}, headers=h).json()["id"]
    r   = client.put(f"/models/{mid}/versions/{vid}", json={"stage": "prod"}, headers=h)
    assert r.status_code == 200
    assert r.json()["stage"] == "prod"

def test_compare_versions(client, tokens):
    h   = auth(tokens["ml"])
    mid = client.post("/models", json={"name": "cmp"}, headers=h).json()["id"]
    client.post(f"/models/{mid}/versions", json={"version": "1.0.0"}, headers=h)
    client.post(f"/models/{mid}/versions", json={"version": "2.0.0"}, headers=h)
    r = client.get(f"/models/{mid}/versions/compare", headers=auth(tokens["viewer"]))
    assert r.status_code == 200
    assert r.json()["total"] == 2


# ── Artifacts ─────────────────────────────────────────────────────────────────

def test_upload_download_artifact(client, tokens):
    h   = auth(tokens["ml"])
    mid = client.post("/models", json={"name": "artm"}, headers=h).json()["id"]
    vid = client.post(f"/models/{mid}/versions", json={"version": "1.0.0"}, headers=h).json()["id"]
    data = b"fake weights"
    aid  = client.post(
        f"/models/{mid}/versions/{vid}/artifacts",
        files={"file": ("model.pkl", io.BytesIO(data), "application/octet-stream")},
        data={"artifact_type": "weights"},
        headers=h,
    ).json()["id"]
    r = client.get(f"/models/{mid}/versions/{vid}/artifacts/{aid}/download",
        headers=auth(tokens["viewer"]))
    assert r.status_code == 200
    assert r.content == data

def test_delete_artifact(client, tokens):
    h_ml    = auth(tokens["ml"])
    h_admin = auth(tokens["admin"])
    mid = client.post("/models", json={"name": "darm"}, headers=h_ml).json()["id"]
    vid = client.post(f"/models/{mid}/versions", json={"version": "1.0.0"}, headers=h_ml).json()["id"]
    aid = client.post(
        f"/models/{mid}/versions/{vid}/artifacts",
        files={"file": ("f.bin", io.BytesIO(b"x"), "application/octet-stream")},
        data={"artifact_type": "w"},
        headers=h_ml,
    ).json()["id"]
    assert client.delete(f"/models/{mid}/versions/{vid}/artifacts/{aid}", headers=h_admin).status_code == 204


# ── Experiment tracking ───────────────────────────────────────────────────────

def test_log_and_get_training_run(client, tokens):
    h   = auth(tokens["ml"])
    mid = client.post("/models", json={"name": "expm"}, headers=h).json()["id"]
    vid = client.post(f"/models/{mid}/versions", json={"version": "1.0.0"}, headers=h).json()["id"]
    r   = client.post(f"/models/{mid}/versions/{vid}/training-run",
        json={"accuracy": 0.94, "f1_score": 0.91, "loss": 0.12, "framework": "pytorch"},
        headers=h,
    )
    assert r.status_code == 201
    assert r.json()["accuracy"] == 0.94
    r2 = client.get(f"/models/{mid}/versions/{vid}/training-run", headers=auth(tokens["viewer"]))
    assert r2.status_code == 200
    assert r2.json()["f1_score"] == 0.91

def test_experiments_filter(client, tokens):
    h   = auth(tokens["ml"])
    mid = client.post("/models", json={"name": "filtm"}, headers=h).json()["id"]
    vid = client.post(f"/models/{mid}/versions", json={"version": "1.0.0", "stage": "prod"}, headers=h).json()["id"]
    client.post(f"/models/{mid}/versions/{vid}/training-run",
        json={"accuracy": 0.95, "f1_score": 0.92, "framework": "sklearn"},
        headers=h,
    )
    r = client.get("/experiments?min_accuracy=0.90", headers=auth(tokens["viewer"]))
    assert r.status_code == 200
    assert r.json()["total"] >= 1
    r2 = client.get("/experiments?min_accuracy=0.99", headers=auth(tokens["viewer"]))
    assert r2.json()["total"] == 0


# ── Audit log ─────────────────────────────────────────────────────────────────

def test_audit_log_records_create(client, tokens):
    client.post("/models", json={"name": "audm"}, headers=auth(tokens["ml"]))
    r = client.get("/audit-logs", headers=auth(tokens["admin"]))
    assert r.status_code == 200
    assert any(l["action"] == "CREATE" for l in r.json()["logs"])

def test_audit_log_records_promote(client, tokens):
    h   = auth(tokens["ml"])
    mid = client.post("/models", json={"name": "audp"}, headers=h).json()["id"]
    vid = client.post(f"/models/{mid}/versions", json={"version": "1.0.0", "stage": "dev"}, headers=h).json()["id"]
    client.put(f"/models/{mid}/versions/{vid}", json={"stage": "prod"}, headers=h)
    r = client.get("/audit-logs?action=PROMOTE", headers=auth(tokens["admin"]))
    assert r.json()["total"] >= 1


# ── Admin role management ─────────────────────────────────────────────────────

def test_admin_list_users(client, tokens):
    r = client.get("/admin/users", headers=auth(tokens["admin"]))
    assert r.status_code == 200
    assert "users" in r.json()

def test_admin_promote_user(client, tokens):
    register(client, "promoteme")
    users = client.get("/admin/users", headers=auth(tokens["admin"])).json()["users"]
    uid   = next(u["id"] for u in users if u["username"] == "promoteme")
    r     = client.put(f"/admin/users/{uid}/role",
        json={"role": "ml_engineer"},
        headers=auth(tokens["admin"]),
    )
    assert r.status_code == 200
    assert r.json()["role"] == "ml_engineer"

def test_admin_deactivate_user(client, tokens):
    register(client, "deactivateme")
    users = client.get("/admin/users", headers=auth(tokens["admin"])).json()["users"]
    uid   = next(u["id"] for u in users if u["username"] == "deactivateme")
    r     = client.delete(f"/admin/users/{uid}", headers=auth(tokens["admin"]))
    assert r.status_code == 200
    assert r.json()["is_active"] == False

def test_admin_cannot_change_own_role(client, tokens):
    users = client.get("/admin/users", headers=auth(tokens["admin"])).json()["users"]
    uid   = next(u["id"] for u in users if u["username"] == "admin_user")
    r     = client.put(f"/admin/users/{uid}/role",
        json={"role": "viewer"},
        headers=auth(tokens["admin"]),
    )
    assert r.status_code == 400


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
