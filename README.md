# MLOps Model Registry

A production-ready Model Registry API built with **FastAPI**, **PostgreSQL**, and pluggable artifact storage backends. Supports JWT authentication, Role-Based Access Control (RBAC), model versioning, and artifact management with local or Google Cloud Storage.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Roles and Permissions](#roles-and-permissions)
- [Environment Variables](#environment-variables)
- [Local Development Setup](#local-development-setup)
- [API Reference](#api-reference)
- [Example Workflow](#example-workflow)
- [Storage Backends](#storage-backends)
- [Future Improvements](#future-improvements)
- [License](#license)

---

## Features

- JWT-based authentication (register, login)
- Role-Based Access Control (viewer / ml_engineer / admin)
- Model CRUD with pagination and name filtering
- Model versioning with stage management (dev / staging / prod / archived)
- Artifact upload and download (any file type)
- SHA256 checksum verification
- PostgreSQL metadata storage
- Alembic database migrations
- Storage abstraction layer — swap local ↔ GCS with one env var
- Local filesystem storage for development
- Google Cloud Storage backend for production
- Swagger UI with OAuth2 authorization
- OpenAPI documentation

---

## Architecture

```
                    ┌─────────────────────────┐
                    │      FastAPI REST API    │
                    │  JWT Auth + RBAC Guard  │
                    └──────────┬──────────────┘
                               │
                 ┌─────────────┴──────────────┐
                 │                            │
                 ▼                            ▼
       ┌──────────────────┐        ┌──────────────────────┐
       │   PostgreSQL     │        │   Storage Backend    │
       │  Model Metadata  │        │  (abstraction layer) │
       │  User + Roles    │        └──────────┬───────────┘
       └──────────────────┘                   │
                                 ┌────────────┴────────────┐
                                 │                         │
                                 ▼                         ▼
                      ┌─────────────────┐      ┌─────────────────────┐
                      │ Local Filesystem │      │ Google Cloud Storage│
                      │ model_artifacts/ │      │ gs://<bucket>/      │
                      └─────────────────┘      └─────────────────────┘
```

**PostgreSQL** stores metadata — model name, version, artifact path, file size, checksum, user roles.

**Storage backend** stores actual binary files — model weights, configs, metrics. Switch between local and GCS with a single environment variable.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| API Framework | FastAPI |
| ORM | SQLAlchemy |
| Database | PostgreSQL 15 |
| Migrations | Alembic |
| Auth | JWT (python-jose) + bcrypt |
| Storage | Local filesystem / Google Cloud Storage |
| Containerization | Docker Compose |
| Runtime | Python 3.10+ |

---

## Project Structure

```
kimchi/
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── d242ad00ce59_init.py
│       └── 43aa7442684c_add_users_table.py
├── app/
│   ├── auth/
│   │   ├── dependencies.py      # get_current_user, require_ml_engineer, require_admin
│   │   ├── security.py          # JWT encode/decode, bcrypt hashing
│   │   └── __init__.py
│   ├── routers/
│   │   ├── auth.py              # /auth/register, /auth/login, /auth/login/swagger
│   │   └── models.py            # All model/version/artifact routes (RBAC protected)
│   ├── storage/
│   │   ├── base.py              # StorageBase abstract class
│   │   ├── local.py             # LocalStorage implementation
│   │   └── gcs.py               # GCSStorage implementation
│   ├── dependencies.py          # get_db(), get_storage()
│   ├── models.py                # SQLAlchemy ORM: Model, ModelVersion, ModelArtifact, User
│   ├── schemas.py               # Pydantic schemas for request/response
│   └── main.py                  # FastAPI app, middleware, router registration
├── tests/
│   ├── test_api.py
│   └── test_storage.py
├── model_artifacts/             # Local storage directory (dev only)
├── docker-compose.yml
├── alembic.ini
├── pyproject.toml
├── .env
└── README.md
```

---

## Roles and Permissions

| Role | GET | POST | PUT | DELETE |
|------|-----|------|-----|--------|
| `viewer` | ✅ | ❌ 403 | ❌ 403 | ❌ 403 |
| `ml_engineer` | ✅ | ✅ | ✅ | ❌ 403 |
| `admin` | ✅ | ✅ | ✅ | ✅ |

All new users registered via `/auth/register` are assigned `viewer` role by default.

To promote a user, update directly in PostgreSQL:

```sql
-- Connect to the running container
docker exec -it modelregistry_postgres psql -U user -d modelregistry

-- Promote to ml_engineer
UPDATE users SET role = 'ml_engineer' WHERE username = 'shivam';

-- Promote to admin
UPDATE users SET role = 'admin' WHERE username = 'shivam';

-- Verify
SELECT username, role, is_active FROM users;
```

---

## Environment Variables

Create a `.env` file in the project root:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost/modelregistry

# JWT Secret — generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your-long-random-secret-key-here

# Storage: "local" for dev, "gcs" for production
STORAGE_BACKEND=gcs

# Required only when STORAGE_BACKEND=gcs
GCS_BUCKET=mlops-model-registry-artifacts
```

**Generate a secure SECRET_KEY:**

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Local Development Setup

### Prerequisites

- Python 3.10+
- Docker and Docker Compose
- `gcloud` CLI (only if using GCS backend)

### 1. Clone Repository

```bash
git clone https://github.com/Upshivam786/mlops-model-registry.git
cd mlops-model-registry
```

### 2. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -U pip
pip install \
  fastapi \
  uvicorn \
  sqlalchemy \
  alembic \
  psycopg2-binary \
  python-multipart \
  google-cloud-storage \
  python-dotenv \
  python-jose[cryptography] \
  passlib[bcrypt]
```

### 4. Configure Environment

```bash
cp .env.example .env
# Edit .env with your values
```

### 5. Start PostgreSQL

```bash
docker compose up -d
```

### 6. Run Database Migrations

```bash
alembic upgrade head
```

### 7. Start API Server

```bash
uvicorn app.main:app --reload
```

API is now running at `http://localhost:8000`

Swagger UI: `http://localhost:8000/docs`

---

## API Reference

### Authentication

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/register` | None | Register new user (role=viewer) |
| POST | `/auth/login` | None | Login with JSON, returns JWT |
| POST | `/auth/login/swagger` | None | Login with form data (Swagger UI) |

### Models

| Method | Endpoint | Required Role | Description |
|--------|----------|--------------|-------------|
| GET | `/models/` | viewer+ | List all models (paginated) |
| POST | `/models/` | ml_engineer+ | Create a new model |
| GET | `/models/{model_id}` | viewer+ | Get model by ID |
| PUT | `/models/{model_id}` | ml_engineer+ | Update model metadata |
| DELETE | `/models/{model_id}` | admin | Delete model and all versions |

### Model Versions

| Method | Endpoint | Required Role | Description |
|--------|----------|--------------|-------------|
| GET | `/models/{id}/versions` | viewer+ | List versions |
| POST | `/models/{id}/versions` | ml_engineer+ | Create new version |
| GET | `/models/{id}/versions/{vid}` | viewer+ | Get version by ID |
| PUT | `/models/{id}/versions/{vid}` | ml_engineer+ | Update version stage/description |
| DELETE | `/models/{id}/versions/{vid}` | admin | Delete version and its artifacts |

### Artifacts

| Method | Endpoint | Required Role | Description |
|--------|----------|--------------|-------------|
| GET | `/models/{id}/versions/{vid}/artifacts` | viewer+ | List artifacts |
| POST | `/models/{id}/versions/{vid}/artifacts` | ml_engineer+ | Upload artifact file |
| GET | `/models/{id}/versions/{vid}/artifacts/{aid}` | viewer+ | Get artifact metadata |
| GET | `/models/{id}/versions/{vid}/artifacts/{aid}/download` | viewer+ | Download artifact file |
| DELETE | `/models/{id}/versions/{vid}/artifacts/{aid}` | admin | Delete artifact |

---

## Example Workflow

This is a complete end-to-end example using a real model file.

### Step 1 — Register and Login

```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"shivam","email":"shivam@example.com","password":"secret123"}'

# Login and store token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"shivam","password":"secret123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo $TOKEN
```

### Step 2 — Create a Model File Locally

```bash
python3 - <<EOF
import pickle

model = {
    "name": "house-price-model",
    "algorithm": "LinearRegression",
    "accuracy": 0.92
}

with open("house_price_model.pkl", "wb") as f:
    pickle.dump(model, f)

print("Model saved: house_price_model.pkl")
EOF
```

### Step 3 — Register the Model

```bash
curl -X POST http://localhost:8000/models/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "house-price-model",
    "description": "Predicts house prices using linear regression",
    "owner": "shivam",
    "tags": "regression,housing,v1"
  }'
```

Response:
```json
{
  "name": "house-price-model",
  "description": "Predicts house prices using linear regression",
  "owner": "shivam",
  "tags": "regression,housing,v1",
  "id": 13,
  "created_at": "2026-06-10T09:45:33.269751",
  "updated_at": "2026-06-10T09:45:33.269753"
}
```

### Step 4 — Create a Version

```bash
curl -X POST http://localhost:8000/models/13/versions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "version": "1.0.0",
    "stage": "dev",
    "description": "Initial training run"
  }'
```

Response:
```json
{
  "version": "1.0.0",
  "stage": "dev",
  "description": "Initial training run",
  "id": 4,
  "model_id": 13,
  "created_at": "2026-06-10T09:45:49.960100",
  "updated_at": "2026-06-10T09:45:49.960101"
}
```

### Step 5 — Upload the Model File

```bash
curl -X POST \
  "http://localhost:8000/models/13/versions/4/artifacts?artifact_type=weights" \
  -H "Authorization: Bearer $TOKEN" \
  -F "artifact_type=weights" \
  -F "file=@house_price_model.pkl"
```

Response:
```json
{
  "artifact_type": "weights",
  "artifact_path": "models/13/versions/4/artifacts/house_price_model.pkl",
  "file_size": 94,
  "checksum": null,
  "id": 4,
  "version_id": 4,
  "created_at": "2026-06-10T09:46:09.752935"
}
```

The file is now stored in GCS:
```
gs://mlops-model-registry-artifacts/models/13/versions/4/artifacts/house_price_model.pkl
```

Verify directly:
```bash
gcloud storage ls -r gs://mlops-model-registry-artifacts/models/**
```

### Step 6 — Download and Load the Model

```bash
# Download
curl "http://localhost:8000/models/13/versions/4/artifacts/4/download" \
  -H "Authorization: Bearer $TOKEN" \
  -o downloaded_model.pkl

# Load and verify
python3 - <<EOF
import pickle

with open("downloaded_model.pkl", "rb") as f:
    model = pickle.load(f)

print(model)
# {'name': 'house-price-model', 'algorithm': 'LinearRegression', 'accuracy': 0.92}
EOF
```

### Step 7 — Promote Version to Production

```bash
curl -X PUT http://localhost:8000/models/13/versions/4 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"stage": "prod"}'
```

---

## Swagger UI Authorization

1. Open `http://localhost:8000/docs`
2. Click **Authorize** (lock icon, top right)
3. Fill in `username` and `password` only — leave `client_id` and `client_secret` blank
4. Click **Authorize**

Swagger calls `/auth/login/swagger` automatically and injects the token into all subsequent requests.

---

## Storage Backends

### Local Filesystem (Development)

```env
STORAGE_BACKEND=local
STORAGE_BASE_PATH=./model_artifacts
```

Files are stored on the server's local disk under `model_artifacts/`. Fast and free, but not suitable for production — files are lost if the server is replaced, and cannot be shared across multiple instances.

### Google Cloud Storage (Production)

```env
STORAGE_BACKEND=gcs
GCS_BUCKET=mlops-model-registry-artifacts
```

Files are stored in a GCS bucket. Durable, scalable, and accessible from anywhere. Requires GCP credentials configured via `gcloud auth application-default login` or a service account key.

Storage path layout:

```
gs://<bucket>/models/<model_id>/versions/<version_id>/artifacts/<filename>
```

Switch between backends by changing `STORAGE_BACKEND` in `.env` and restarting the server. No code changes required.

---

## RBAC Verification

Quick test to confirm all three roles are enforced:

```bash
# 401 — no token
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/models/

# 403 — viewer cannot create
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/models/ \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"test"}'

# 200 — viewer can read
curl -s -o /dev/null -w "%{http_code}" \
  http://localhost:8000/models/ \
  -H "Authorization: Bearer $VIEWER_TOKEN"

# 201 — ml_engineer can create
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/models/ \
  -H "Authorization: Bearer $ML_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"test"}'

# 403 — ml_engineer cannot delete
curl -s -o /dev/null -w "%{http_code}" \
  -X DELETE http://localhost:8000/models/1 \
  -H "Authorization: Bearer $ML_TOKEN"

# 204 — admin can delete
curl -s -o /dev/null -w "%{http_code}" \
  -X DELETE http://localhost:8000/models/1 \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

Expected: `401`, `403`, `200`, `201`, `403`, `204`

---
---

## Phase 2 — Audit Logging (Completed)

Every write action in the system now produces an immutable record stored in the audit_logs table.

### New files
- app/audit.py — write_audit_log() helper
- app/routers/audit.py — GET /audit-logs endpoint
- alembic/versions/add_audit_logs_table.py — DB migration

### Modified files
- app/models.py — AuditLog ORM added
- app/routers/models.py — audit logging wired into every write route
- app/schemas.py — AuditLogRead and AuditLogList schemas added
- app/main.py — audit router registered, version bumped to 0.2.0

### Audit log endpoint

GET /audit-logs                        (admin only)
GET /audit-logs?action=PROMOTE
GET /audit-logs?resource_type=model_version
GET /audit-logs?username=shivam

### Actions tracked
CREATE   — model, version, or artifact created
UPDATE   — metadata changed
DELETE   — resource deleted
PROMOTE  — version stage changed (dev → staging → prod → archived)

### Run migration
alembic upgrade head
## Future Improvements

- S3 Storage Backend (AWS)
- Signed Download URLs (time-limited GCS links)
- Artifact Checksum Verification (SHA256 on upload)
- Model Promotion Workflow (dev → staging → prod approval gates)
- Admin endpoint for role management (no direct DB access needed)
- MLflow Integration
- Kubernetes Deployment manifests
- CI/CD Pipeline (GitHub Actions)
- Terraform Infrastructure as Code
- Audit Logging (who created/deleted what and when)
- Token refresh endpoint
- Rate limiting

---

## License

MIT License
