# MLOps Model Registry

A production-ready Model Registry built with FastAPI, PostgreSQL, and pluggable artifact storage backends.

This project provides a centralized repository for storing, versioning, and managing machine learning models and their artifacts.

## Features

* Model management (CRUD operations)
* Model versioning
* Artifact upload and download
* PostgreSQL metadata storage
* Alembic database migrations
* Storage abstraction layer
* Local filesystem storage
* Google Cloud Storage (GCS) backend
* REST API with OpenAPI documentation
* FastAPI dependency injection architecture

---

## Architecture

```text
                    ┌─────────────────────┐
                    │      FastAPI        │
                    │      REST API       │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Service Layer     │
                    └──────────┬──────────┘
                               │
                 ┌─────────────┴─────────────┐
                 │                           │
                 ▼                           ▼

       ┌─────────────────┐        ┌─────────────────┐
       │   PostgreSQL    │        │ Storage Backend │
       │ Model Metadata  │        └────────┬────────┘
       └─────────────────┘                 │
                                           │
                    ┌──────────────────────┴──────────────────────┐
                    │                                             │
                    ▼                                             ▼

          ┌───────────────────┐                  ┌───────────────────┐
          │ Local Filesystem  │                  │ Google Cloud      │
          │ model_artifacts/  │                  │ Storage (GCS)     │
          └───────────────────┘                  └───────────────────┘
```

---

## Tech Stack

* Python 3.10+
* FastAPI
* SQLAlchemy
* PostgreSQL
* Alembic
* Google Cloud Storage
* Docker Compose

---

## Project Structure

```text
.
├── alembic/
├── app/
│   ├── routers/
│   ├── storage/
│   │   ├── base.py
│   │   ├── local.py
│   │   └── gcs.py
│   ├── dependencies.py
│   ├── models.py
│   ├── schemas.py
│   └── main.py
├── model_artifacts/
├── tests/
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## Environment Variables

Create a `.env` file:

```env
DATABASE_URL=postgresql://user:password@localhost/modelregistry

STORAGE_BACKEND=gcs

GCS_BUCKET=mlops-model-registry-artifacts
```

### Local Storage

```env
STORAGE_BACKEND=local
```

### Google Cloud Storage

```env
STORAGE_BACKEND=gcs
GCS_BUCKET=mlops-model-registry-artifacts
```

---

## Local Development Setup

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
python-dotenv
```

### 4. Start PostgreSQL

```bash
docker compose up -d
```

### 5. Run Database Migrations

```bash
alembic upgrade head
```

### 6. Start API

```bash
uvicorn app.main:app --reload
```

---

## API Documentation

Swagger UI:

```text
http://localhost:8000/docs
```

OpenAPI JSON:

```text
http://localhost:8000/openapi.json
```

---

## Example Workflow

### Create Model

```bash
curl -X POST \
"http://localhost:8000/models/" \
-H "Content-Type: application/json" \
-d '{
  "name":"sentiment-model",
  "description":"NLP sentiment classifier"
}'
```

### Create Version

```bash
curl -X POST \
"http://localhost:8000/models/1/versions" \
-H "Content-Type: application/json" \
-d '{
  "version":"1.0.0"
}'
```

### Upload Artifact

```bash
curl -X POST \
"http://localhost:8000/models/1/versions/1/artifacts" \
-F "artifact_type=model" \
-F "file=@model.pkl"
```

---

## Storage Backends

### Local Filesystem

Artifacts stored in:

```text
model_artifacts/
```

### Google Cloud Storage

Artifacts stored in:

```text
gs://<bucket-name>/models/<model-id>/versions/<version-id>/artifacts/
```

Verified with:

```text
gs://mlops-model-registry-artifacts/models/6/versions/3/artifacts/model.txt
```

---

## Future Improvements

* S3 Storage Backend
* Model Promotion Workflow
* Authentication & Authorization
* Signed Download URLs
* Artifact Checksums
* MLflow Integration
* Kubernetes Deployment
* CI/CD Pipeline
* Terraform Infrastructure
* Audit Logging

---

## License

MIT License
