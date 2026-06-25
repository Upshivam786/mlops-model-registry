# MLOps Model Registry

**Author: Shivam Upadhyay**
**GitHub: [Upshivam786/mlops-model-registry](https://github.com/Upshivam786/mlops-model-registry)**
**Version: 0.5.0**

A production-grade MLOps Model Registry built from scratch with **FastAPI**, **PostgreSQL**, **Google Cloud Storage**, **JWT Authentication**, **Role-Based Access Control**, **Audit Logging**, **Experiment Tracking**, a **Python SDK**, **CI/CD**, and **Governance features** (model cards, data lineage, signed download URLs). Designed and implemented to manage the complete machine learning model lifecycle — from experiment to production.

---

## Table of Contents

- [What This Project Does](#what-this-project-does)
- [What Was Built — Phase by Phase](#what-was-built--phase-by-phase)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Database Schema](#database-schema)
- [Roles and Permissions](#roles-and-permissions)
- [Environment Variables](#environment-variables)
- [Local Development Setup](#local-development-setup)
- [API Reference](#api-reference)
- [End-to-End Workflow](#end-to-end-workflow)
- [Storage Backends](#storage-backends)
- [Roadmap](#roadmap)
- [License](#license)

---

## What This Project Does

Most ML teams manage models by saving files to Google Drive, shared folders, or individual developer machines. This creates real operational problems: nobody knows which model is in production, rollback requires hunting for old files, there is no record of who deployed what and when, and experiments cannot be compared without opening every file manually.

This platform solves all of that. It is a centralised Model Registry that:

- Tracks every model, version, and artifact with full metadata in PostgreSQL
- Stores actual model files (weights, configs, metrics) in Google Cloud Storage
- Enforces role-based access so only authorised users can promote or delete models
- Writes an immutable audit log for every write action in the system
- Records training hyperparameters and metrics as queryable database fields
- Exposes a clean REST API with Swagger UI documentation

The separation between metadata (PostgreSQL) and artifacts (GCS) follows the same pattern used by MLflow, SageMaker Model Registry, and Weights & Biases.

---

## What Was Built — Phase by Phase

### Phase 1 — Foundation (v0.1.0) ✅

Built the complete core platform:

- Model registration and CRUD with pagination and name filtering
- Model versioning with stage lifecycle: `dev → staging → prod → archived`
- Artifact upload and download backed by Google Cloud Storage
- Storage abstraction layer — swap between local filesystem and GCS with a single environment variable
- PostgreSQL metadata storage with Alembic migrations
- JWT authentication — register, login, token generation
- Role-Based Access Control — three roles with enforced HTTP method permissions
- Swagger UI with OAuth2 authorization
- Docker Compose for local PostgreSQL

**Verified:**

```
401  — unauthenticated request blocked
403  — viewer cannot POST /models
200  — viewer can GET /models
201  — ml_engineer can POST /models
403  — ml_engineer cannot DELETE /models/{id}
204  — admin can DELETE /models/{id}
```

File uploaded to GCS, downloaded back, loaded into Python — byte-for-byte identical.

---

### Phase 2 — Audit Logging (v0.2.0) ✅

Every write action in the system now produces an immutable record in the `audit_logs` table. Built:

- `AuditLog` ORM table with `user_id`, `username`, `action`, `resource_type`, `resource_id`, `old_value`, `new_value`, `timestamp`
- `write_audit_log()` helper — called inside every mutating route using `db.flush()` so the audit entry and the actual change are in the same transaction
- `PROMOTE` action automatically detected when a version stage changes
- `GET /audit-logs` endpoint — admin only, with filters by action, resource type, and username
- Alembic migration for the `audit_logs` table

**Actions tracked:**

| Action | When |
|--------|------|
| `CREATE` | Model, version, or artifact created |
| `UPDATE` | Metadata changed |
| `DELETE` | Any resource deleted |
| `PROMOTE` | Version stage changed (dev → staging → prod → archived) |

**Verified output:**

```json
{
  "logs": [
    {
      "action": "PROMOTE",
      "resource_type": "model_version",
      "resource_id": 5,
      "old_value": "{\"stage\": \"staging\"}",
      "new_value": "{\"stage\": \"prod\"}",
      "username": "shivam",
      "timestamp": "2026-06-16T05:01:42.636362"
    },
    {
      "action": "PROMOTE",
      "resource_type": "model_version",
      "resource_id": 5,
      "old_value": "{\"stage\": \"dev\"}",
      "new_value": "{\"stage\": \"staging\"}",
      "username": "shivam",
      "timestamp": "2026-06-16T05:01:33.590317"
    }
  ],
  "total": 2,
  "page": 1,
  "size": 50
}
```

---

### Phase 3 — Experiment Tracking (v0.3.0) ✅

Training metadata, hyperparameters, and evaluation metrics are now first-class queryable fields in PostgreSQL — not buried inside artifact files. Built:

- `TrainingRun` ORM table with indexed `accuracy` and `f1_score` columns for fast querying
- `POST /models/{id}/versions/{vid}/training-run` — log a training run (one per version, overwrites if called again)
- `GET /models/{id}/versions/{vid}/training-run` — retrieve training run for a version
- `GET /models/{id}/versions/compare` — compare all versions of a model side by side, sorted by accuracy
- `GET /experiments` — query training runs across all models with metric filters, stage filter, framework filter, and sort
- Alembic migration for the `training_runs` table

**Verified queries:**

```bash
# All experiments with accuracy above 0.90
GET /experiments?min_accuracy=0.90

# All prod experiments sorted by F1 score
GET /experiments?stage=prod&sort_by=f1_score&order=desc

# Compare all versions of a specific model
GET /models/15/versions/compare
```

**Verified output:**

```json
{
  "experiments": [
    {
      "version": "1.0.0",
      "stage": "prod",
      "model_name": "audit-test-model",
      "accuracy": 0.94,
      "f1_score": 0.91,
      "loss": 0.12,
      "learning_rate": 0.001,
      "epochs": 50,
      "batch_size": 32,
      "dataset_name": "invoices-q1-2026",
      "framework": "pytorch",
      "training_duration": 3600,
      "created_by": "shivam"
    }
  ],
  "total": 1,
  "page": 1,
  "size": 50
}
```

---

### Phase 4 — SDK, CI/CD, Role Management, Refresh Tokens (v0.4.0) ✅

Adds the tooling and operational pieces that turn a working API into a
maintainable platform: a Python client, automated testing on every push,
self-service role management, and longer-lived sessions.

- **Python SDK** — `sdk/kimchi_sdk/client.py`, a `ModelRegistry` class
  wrapping every API endpoint so consumers don't have to hand-write curl
  or `requests` calls.
- **GitHub Actions CI** — runs the full test suite on every push using
  SQLite in-memory, no PostgreSQL container required in CI. `bcrypt==4.0.1`
  and `passlib[bcrypt]==1.7.4` are pinned in both `pyproject.toml` and the
  workflow file — newer bcrypt releases break passlib's bundled compat
  layer, so this pin is load-bearing, not cosmetic.
- **Admin role management** — `GET /admin/users`, `PUT
  /admin/users/{id}/role`, `DELETE /admin/users/{id}` remove the need for
  direct database access to promote or deactivate users. (The very first
  admin in a fresh environment still requires one direct DB write — see
  `docs/troubleshooting.md` for the bootstrap pattern.)
- **Refresh tokens** — `POST /auth/refresh`; access tokens now expire in
  60 minutes, refresh tokens in 7 days, and `/auth/login` returns both.

**Verified:**

```
201 — SDK client successfully creates a model end-to-end
38  — tests passing in GitHub Actions on every push
200 — GET /admin/users (admin only)
200 — PUT /admin/users/{id}/role promotes a user
403 — admin cannot change their own role (self-demotion guard)
200 — POST /auth/refresh returns a new access token from a valid refresh token
```

---

### Phase 5 — Monitoring and Governance (v0.5.0) ✅

Adds three governance and operability features on top of the existing
platform: direct-from-storage downloads, structured model documentation,
and dataset-to-model traceability.

- **Signed GCS Download URLs (5A)** — the artifact download endpoint now
  tries to generate a time-limited V4 signed URL first, so large files
  transfer directly from GCS to the client instead of streaming through
  the API process. Falls back to the original streaming behavior
  automatically when the storage backend doesn't support it (local dev)
  or signing fails for any reason — the fallback never raises an error to
  the caller. See `docs/troubleshooting.md` for the most common reason
  signing fails (Application Default Credentials lacking a private key).
- **Model Cards (5B)** — a new `model_cards` table, one per model version,
  capturing intended use, limitations, ethical considerations, training
  data summary, evaluation summary, and recommendations. `ml_engineer+`
  can create and update a card; deleting one is admin-only.
- **Data Lineage (5C)** — a new `dataset_links` table connects model
  versions to the datasets that trained, validated, or tested them. Query
  in either direction: `GET /lineage/version/{id}` for "what data fed this
  model," or `GET /lineage/dataset/{hash}` for "which deployed models used
  this dataset" — the latter is the query you'd run if a dataset turns out
  to be biased, leaked, or otherwise compromised after the fact.

**Verified:**

```
201 — create model card
200 — get / update model card
400 — duplicate model card create rejected
204 — admin-only model card delete
403 — viewer and ml_engineer blocked from deleting a card
201 — link dataset to a version
200 — list datasets linked to a version
204 — delete a dataset link (admin only)
200 — lineage by dataset hash (joins dataset_links → model_versions → models)
404 — lineage by dataset hash with no matches
200 — lineage by version id
307 — signed URL redirect when GCS signing succeeds
200 — streamed fallback when signing is unavailable or fails
```

64 tests passing (45 carried over from Phases 1–4, plus 19 new for Phase 5),
0 regressions. Migration chain verified end-to-end on PostgreSQL —
`b2c3d4e5f6a7 → c3d4e5f6a7b8`, with upgrade, downgrade, and re-upgrade all
confirmed clean. Full step-by-step curl walkthrough in
`docs/phase5_governance_testing.md`.

---

## Architecture

```
                    ┌──────────────────────────────────┐
                    │         FastAPI REST API          │
                    │   JWT Auth · RBAC · Swagger UI   │
                    └───────────────┬──────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
   ┌────────────────┐    ┌────────────────────┐   ┌─────────────────┐
   │   PostgreSQL   │    │   Storage Backend  │   │   Audit Logger  │
   │                │    │  (abstraction)     │   │                 │
   │ models         │    └─────────┬──────────┘   │ Every write     │
   │ model_versions │              │              │ action logged   │
   │ model_artifacts│    ┌─────────┴──────────┐   │ with old/new    │
   │ users          │    │                    │   │ values          │
   │ audit_logs     │    ▼                    ▼   └─────────────────┘
   │ training_runs  │  Local FS            GCS
   └────────────────┘  (dev)           (production)
```

**PostgreSQL** stores all metadata — model names, version stages, artifact paths, user roles, audit entries, training metrics. Nothing binary lives here.

**Storage backend** stores actual files — model weights, configs, tokenizers, evaluation outputs. Switch between local and GCS by changing one environment variable.

**Audit logger** runs inside every mutating route, writing to `audit_logs` in the same database transaction as the actual change. If the change fails, the audit entry is also rolled back.

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| API Framework | FastAPI 0.100+ |
| ORM | SQLAlchemy |
| Database | PostgreSQL 15 |
| Migrations | Alembic |
| Authentication | JWT via python-jose + bcrypt |
| Storage | Local filesystem / Google Cloud Storage |
| Containerisation | Docker Compose |
| Runtime | Python 3.10+ |

---

## Project Structure

```
mlops-model-registry/
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── d242ad00ce59_init.py
│       ├── 43aa7442684c_add_users_table.py
│       ├── add_audit_logs_table.py                    ← Phase 2
│       ├── add_training_runs_table.py                 ← Phase 3
│       └── add_model_cards_and_dataset_links.py        ← Phase 5
├── app/
│   ├── auth/
│   │   ├── dependencies.py    # get_current_user, require_ml_engineer, require_admin
│   │   ├── security.py        # JWT encode/decode, bcrypt hashing
│   │   └── __init__.py
│   ├── routers/
│   │   ├── auth.py            # /auth/register, /auth/login, /auth/login/swagger, /auth/refresh
│   │   ├── models.py          # All model/version/artifact routes + compare + signed download
│   │   ├── audit.py           # GET /audit-logs (Phase 2)
│   │   ├── experiments.py     # POST/GET training-run, GET /experiments (Phase 3)
│   │   ├── admin.py           # User role management (Phase 4)
│   │   ├── model_cards.py     # POST/GET/PUT/DELETE /card (Phase 5)
│   │   └── lineage.py         # Dataset links + lineage queries (Phase 5)
│   ├── storage/
│   │   ├── base.py            # StorageBase abstract class + get_signed_url() default (Phase 5)
│   │   ├── local.py           # LocalStorage implementation
│   │   └── gcs.py             # GCSStorage implementation + get_signed_url() (Phase 5)
│   ├── audit.py               # write_audit_log() helper (Phase 2)
│   ├── dependencies.py        # get_db(), get_storage()
│   ├── models.py              # ORM: Model, ModelVersion, ModelArtifact, User, AuditLog,
│   │                          #      TrainingRun, ModelCard, DatasetLink
│   ├── schemas.py             # All Pydantic request/response schemas
│   └── main.py                # FastAPI app, middleware, router registration
├── sdk/                                                ← Phase 4
│   ├── kimchi_sdk/
│   │   ├── __init__.py
│   │   └── client.py          # ModelRegistry client class
│   └── setup.py
├── docs/
│   ├── phase2_audit_log_testing.md
│   ├── phase3_experiment_tracking_testing.md
│   ├── phase5_governance_testing.md                    ← Phase 5
│   └── troubleshooting.md                              ← Phase 5
├── tests/
│   ├── test_api.py            # 64 tests: Phases 1–5
│   └── test_storage.py
├── .github/workflows/
│   └── ci.yml                                          ← Phase 4
├── model_artifacts/           # Local storage directory (dev only)
├── docker-compose.yml
├── alembic.ini
├── pyproject.toml
├── .env.example
└── README.md
```

---

## Database Schema

```
models
├── id, name (unique), description, owner, tags
└── created_at, updated_at

model_versions
├── id, model_id (FK), version, stage
├── description
└── created_at, updated_at

model_artifacts
├── id, version_id (FK), artifact_type, artifact_path
├── file_size, checksum
└── created_at

users
├── id, username (unique), email (unique)
├── hashed_password, role, is_active
└── created_at

audit_logs                          ← Phase 2
├── id, user_id (FK), username
├── action (CREATE|UPDATE|DELETE|PROMOTE)
├── resource_type, resource_id
├── old_value (JSON), new_value (JSON)
└── timestamp (indexed)

training_runs                       ← Phase 3
├── id, version_id (FK, unique)
├── dataset_name, dataset_hash
├── hyperparameters (JSON), learning_rate, epochs, batch_size
├── metrics (JSON), accuracy (indexed), f1_score (indexed), loss
├── framework, framework_version, training_duration
├── created_by
└── created_at (indexed)

model_cards                         ← Phase 5
├── id, version_id (FK, unique)
├── intended_use, limitations, ethical_considerations
├── training_data_summary, evaluation_summary
├── caveats_and_recommendations
├── created_by
└── created_at, updated_at

dataset_links                       ← Phase 5
├── id, version_id (FK, indexed)
├── dataset_name, dataset_hash (indexed), dataset_uri
├── role (training|validation|test), row_count, notes
├── linked_by
└── created_at (indexed)
```

---

## Roles and Permissions

| Role | GET | POST | PUT | DELETE | Audit Log |
|------|-----|------|-----|--------|-----------|
| `viewer` | ✅ | ❌ 403 | ❌ 403 | ❌ 403 | ❌ 403 |
| `ml_engineer` | ✅ | ✅ | ✅ | ❌ 403 | ❌ 403 |
| `admin` | ✅ | ✅ | ✅ | ✅ | ✅ |

All new users registered via `/auth/register` receive `viewer` role by default. Role changes require direct DB access or an admin endpoint (planned for Phase 4).

```sql
-- Connect to running container
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

```env
# Database
DATABASE_URL=postgresql://user:password@localhost/modelregistry

# JWT Secret — generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your-long-random-secret-key-here

# Storage backend: "local" for dev, "gcs" for production
STORAGE_BACKEND=gcs

# Required only when STORAGE_BACKEND=gcs
GCS_BUCKET=mlops-model-registry-artifacts
```

Generate a secure SECRET_KEY:

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

### 6. Run Migrations

```bash
alembic upgrade head
```

### 7. Start API Server

```bash
uvicorn app.main:app --reload
```

API: `http://localhost:8000`
Swagger UI: `http://localhost:8000/docs`

---

## API Reference

### Authentication

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/register` | None | Register new user (role=viewer) |
| POST | `/auth/login` | None | Login with JSON body, returns JWT |
| POST | `/auth/login/swagger` | None | Login with form data for Swagger UI |

### Models

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| GET | `/models` | viewer+ | List all models (paginated, filterable by name) |
| POST | `/models` | ml_engineer+ | Create a new model |
| GET | `/models/{model_id}` | viewer+ | Get model by ID |
| PUT | `/models/{model_id}` | ml_engineer+ | Update model metadata |
| DELETE | `/models/{model_id}` | admin | Delete model and all versions/artifacts |

### Model Versions

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| GET | `/models/{id}/versions` | viewer+ | List versions (filterable by stage) |
| POST | `/models/{id}/versions` | ml_engineer+ | Create new version |
| GET | `/models/{id}/versions/compare` | viewer+ | Compare all versions with metrics |
| GET | `/models/{id}/versions/{vid}` | viewer+ | Get version by ID |
| PUT | `/models/{id}/versions/{vid}` | ml_engineer+ | Update stage or description |
| DELETE | `/models/{id}/versions/{vid}` | admin | Delete version and its artifacts |

### Artifacts

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| POST | `/models/{id}/versions/{vid}/artifacts` | ml_engineer+ | Upload artifact file |
| GET | `/models/{id}/versions/{vid}/artifacts` | viewer+ | List artifacts |
| GET | `/models/{id}/versions/{vid}/artifacts/{aid}` | viewer+ | Get artifact metadata |
| GET | `/models/{id}/versions/{vid}/artifacts/{aid}/download` | viewer+ | Download artifact file |
| DELETE | `/models/{id}/versions/{vid}/artifacts/{aid}` | admin | Delete artifact from DB and storage |

### Experiment Tracking

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| POST | `/models/{id}/versions/{vid}/training-run` | ml_engineer+ | Log training run for a version |
| GET | `/models/{id}/versions/{vid}/training-run` | viewer+ | Get training run for a version |
| GET | `/experiments` | viewer+ | Query runs across all models |

### Audit Logs

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| GET | `/audit-logs` | admin | Full audit log with filters |

Audit log filters: `?action=PROMOTE`, `?resource_type=model_version`, `?username=shivam`, `?page=2&size=20`

Experiment filters: `?min_accuracy=0.90`, `?min_f1=0.85`, `?max_loss=0.2`, `?stage=prod`, `?framework=pytorch`, `?dataset_name=invoices-q1-2026`, `?sort_by=f1_score&order=desc`

### Admin (Phase 4)

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| GET | `/admin/users` | admin | List all users |
| PUT | `/admin/users/{id}/role` | admin | Change a user's role |
| DELETE | `/admin/users/{id}` | admin | Deactivate a user (admin cannot change their own role) |

### Model Cards (Phase 5)

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| POST | `/models/{id}/versions/{vid}/card` | ml_engineer+ | Create a model card (one per version) |
| GET | `/models/{id}/versions/{vid}/card` | viewer+ | Get the model card for a version |
| PUT | `/models/{id}/versions/{vid}/card` | ml_engineer+ | Update an existing model card |
| DELETE | `/models/{id}/versions/{vid}/card` | admin | Delete a model card |

### Data Lineage (Phase 5)

| Method | Endpoint | Role | Description |
|--------|----------|------|-------------|
| POST | `/models/{id}/versions/{vid}/datasets` | ml_engineer+ | Link a dataset to a version |
| GET | `/models/{id}/versions/{vid}/datasets` | viewer+ | List datasets linked to a version |
| DELETE | `/models/{id}/versions/{vid}/datasets/{link_id}` | admin | Remove a dataset link |
| GET | `/lineage/dataset/{hash}` | viewer+ | All model versions that used a dataset |
| GET | `/lineage/version/{vid}` | viewer+ | All datasets that fed a specific version |

---

## End-to-End Workflow

Complete example: training a model locally, registering it, uploading to GCS, logging metrics, promoting to production.

### Step 1 — Register and Login

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"shivam","email":"shivam@example.com","password":"secret123"}'

TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"shivam","password":"secret123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

### Step 2 — Create a Model File

```bash
python3 - <<EOF
import pickle
model = {"algorithm": "LinearRegression", "accuracy": 0.92}
with open("house_price_model.pkl", "wb") as f:
    pickle.dump(model, f)
print("Saved: house_price_model.pkl")
EOF
```

### Step 3 — Register the Model

```bash
curl -X POST http://localhost:8000/models \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"house-price-model","description":"Predicts house prices","owner":"shivam","tags":"regression,housing"}'
```

### Step 4 — Create a Version

```bash
curl -X POST http://localhost:8000/models/1/versions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"version":"1.0.0","stage":"dev","description":"Initial training run"}'
```

### Step 5 — Upload the Model File

```bash
curl -X POST \
  "http://localhost:8000/models/1/versions/1/artifacts" \
  -H "Authorization: Bearer $TOKEN" \
  -F "artifact_type=weights" \
  -F "file=@house_price_model.pkl"
```

File is now stored in GCS:
```
gs://mlops-model-registry-artifacts/models/1/versions/1/artifacts/house_price_model.pkl
```

### Step 6 — Log Training Metrics

```bash
curl -X POST \
  http://localhost:8000/models/1/versions/1/training-run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_name": "housing-data-q1-2026",
    "dataset_hash": "sha256-abc123",
    "hyperparameters": {"lr": 0.001, "epochs": 50, "batch_size": 32},
    "metrics": {"accuracy": 0.94, "f1_score": 0.91, "loss": 0.12},
    "accuracy": 0.94,
    "f1_score": 0.91,
    "loss": 0.12,
    "framework": "pytorch",
    "framework_version": "2.1.0",
    "training_duration": 3600
  }'
```

### Step 7 — Promote to Production

```bash
# dev → staging
curl -X PUT http://localhost:8000/models/1/versions/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"stage":"staging"}'

# staging → prod
curl -X PUT http://localhost:8000/models/1/versions/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"stage":"prod"}'
```

Both promotions are logged automatically in the audit table.

### Step 8 — Query Best Experiments

```bash
# Who has the best accuracy across all models?
curl -s "http://localhost:8000/experiments?sort_by=accuracy&order=desc" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# What's in production with F1 above 0.85?
curl -s "http://localhost:8000/experiments?stage=prod&min_f1=0.85" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

### Step 9 — Download and Load the Model

```bash
curl "http://localhost:8000/models/1/versions/1/artifacts/1/download" \
  -H "Authorization: Bearer $TOKEN" \
  -o retrieved_model.pkl

python3 - <<EOF
import pickle
with open("retrieved_model.pkl", "rb") as f:
    model = pickle.load(f)
print(model)
EOF
```

### Step 10 — Emergency Rollback

```bash
# Something is wrong with v2.0.0 in prod — revert to v1.0.0
curl -X PUT http://localhost:8000/models/1/versions/2 \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"stage":"archived"}'

curl -X PUT http://localhost:8000/models/1/versions/1 \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"stage":"prod"}'
```

Total rollback time: under 2 minutes. No SSH, no file transfers, no deployment pipeline.

---

## Storage Backends

### Local Filesystem — Development

```env
STORAGE_BACKEND=local
STORAGE_BASE_PATH=./model_artifacts
```

Files stored on the server's local disk. Fast and free, but not suitable for production — files are lost if the server is replaced.

### Google Cloud Storage — Production

```env
STORAGE_BACKEND=gcs
GCS_BUCKET=mlops-model-registry-artifacts
```

Files stored in a GCS bucket. Durable, scalable, accessible from anywhere. Storage path layout:

```
gs://<bucket>/models/<model_id>/versions/<version_id>/artifacts/<filename>
```

Requires GCP credentials via `gcloud auth application-default login` or a service account key. No code changes needed to switch — change the env var and restart.

---

## Roadmap

### Phase 6 — Infrastructure and Monitoring (Planned)

- Kubernetes deployment manifests
- Terraform infrastructure as code
- S3 / MinIO storage backend (AWS)
- Multi-environment deployment (dev / staging / prod namespaces)
- SSO / LDAP role integration
- Model drift detection integration *(carried over from the original
  Phase 5 scope — not yet built; Phase 5 shipped model cards, data
  lineage, and signed URLs only)*
- Performance monitoring hooks *(same as above)*

---

## Swagger UI Authorization

1. Open `http://localhost:8000/docs`
2. Click **Authorize** (lock icon, top right)
3. Fill in `username` and `password` — leave `client_id` and `client_secret` blank
4. Click **Authorize**

Swagger calls `/auth/login/swagger` and injects the token into all subsequent requests automatically.

---

## License

MIT License

Copyright (c) 2026 Shivam Upadhyay
