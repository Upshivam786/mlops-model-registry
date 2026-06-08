# Model Registry - MLOps Component

## Overview

Model Registry is a lightweight MLOps service built with FastAPI and PostgreSQL that enables teams to register, version, and manage machine learning models and their associated artifacts.

The system provides:

* Model registration and metadata management
* Model versioning
* Artifact upload and download
* PostgreSQL-backed metadata storage
* OpenAPI/Swagger documentation
* Dockerized database deployment

---

## Architecture

```text
                FastAPI
                   │
                   ▼
          Model Registry API
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
   PostgreSQL         Local Storage
    Metadata            Artifacts
```

### Components

* FastAPI – REST API layer
* PostgreSQL – Stores model metadata
* SQLAlchemy – ORM layer
* Alembic – Database migrations
* Local Filesystem Storage – Stores model artifacts
* Docker Compose – Database orchestration

---

## Features

### Model Management

* Create models
* Update models
* Delete models
* List models

### Version Management

* Create model versions
* Track version stages (dev, staging, production)
* Manage version metadata

### Artifact Management

* Upload model artifacts
* Download artifacts
* List stored artifacts
* Maintain artifact metadata

---

## Project Structure

```text
.
├── app/
├── alembic/
├── model_artifacts/
├── tests/
├── docker-compose.yml
├── alembic.ini
└── pyproject.toml
```

---

## Local Setup

### Prerequisites

* Python 3.10+
* Docker & Docker Compose

### Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### Install Dependencies

```bash
pip install fastapi sqlalchemy alembic psycopg2-binary uvicorn python-multipart pytest httpx
```

### Start PostgreSQL

```bash
docker compose up -d
```

### Apply Database Migrations

```bash
alembic upgrade head
```

### Start API Server

```bash
uvicorn app.main:app --reload
```

---

## API Documentation

After startup:

Swagger UI:

http://localhost:8000/docs

ReDoc:

http://localhost:8000/redoc

---

## Example Workflow

1. Create a model
2. Create a version
3. Upload model artifacts
4. List stored artifacts
5. Download artifacts

Example hierarchy:

```text
sentiment-model
└── 1.0.0
    └── test.txt
```

---

## Future Improvements

* S3 / MinIO storage backend
* JWT authentication
* Model promotion workflow
* CI/CD pipelines
* Kubernetes deployment
* Model lineage tracking

---

## License

MIT
