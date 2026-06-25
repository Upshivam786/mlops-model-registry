# Phase 5 — Monitoring and Governance Test Guide

Complete command-by-command verification of signed download URLs, model
cards, and data lineage.

## Prerequisites

Server is running:
```bash
uvicorn app.main:app --reload
```

Migration has been applied:
```bash
alembic upgrade head
```

Confirm you're on `c3d4e5f6a7b8` (or later):
```bash
docker exec -it modelregistry_postgres psql -U user -d modelregistry \
  -c "SELECT version_num FROM alembic_version;"
```

Confirm the app is actually serving v0.5.0 before testing anything —
this caught a real stale-server bug during Phase 5 development (see
`docs/troubleshooting.md` if this doesn't match):
```bash
curl -s http://localhost:8000/openapi.json | python3 -c \
  "import sys,json; print(json.load(sys.stdin)['info']['version'])"
```
Expected: `0.5.0`

---

## Step 1 — Get a token

Use any existing user, or register + promote a fresh one:

```bash
curl -s -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"phase5tester","email":"phase5tester@test.com","password":"TestPass123!"}'

docker exec -it modelregistry_postgres psql -U user -d modelregistry \
  -c "UPDATE users SET role = 'admin' WHERE username = 'phase5tester';"

TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"phase5tester","password":"TestPass123!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Token acquired: ${TOKEN:0:20}..."
```

---

## Step 2 — Create a model + version to test against

```bash
MODEL_ID=$(curl -s -X POST http://localhost:8000/models \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"name":"phase5-test-model","description":"verifying phase 5"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

VERSION_ID=$(curl -s -X POST http://localhost:8000/models/$MODEL_ID/versions \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"version":"1.0.0","stage":"dev"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "model_id=$MODEL_ID version_id=$VERSION_ID"
```

Expected: both variables non-empty integers. If either is empty, stop —
everything downstream will 404. See `docs/troubleshooting.md`, section
"Every Phase 5 request returns 404."

---

## Step 3 — Create a model card (5B)

```bash
curl -s -X POST http://localhost:8000/models/$MODEL_ID/versions/$VERSION_ID/card \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"intended_use":"Demonstration only","limitations":"Not for production use"}' \
  | python3 -m json.tool
```

Expected:
```json
{
    "id": 1,
    "version_id": 5,
    "intended_use": "Demonstration only",
    "limitations": "Not for production use",
    "ethical_considerations": null,
    "training_data_summary": null,
    "evaluation_summary": null,
    "caveats_and_recommendations": null,
    "created_by": "phase5tester",
    "created_at": "...",
    "updated_at": "..."
}
```

---

## Step 4 — Get the model card

```bash
curl -s http://localhost:8000/models/$MODEL_ID/versions/$VERSION_ID/card \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected: same object as Step 3.

---

## Step 5 — Update the model card

```bash
curl -s -X PUT http://localhost:8000/models/$MODEL_ID/versions/$VERSION_ID/card \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"limitations":"Updated limitation text"}' | python3 -m json.tool
```

Expected: `limitations` changed, `created_at` unchanged, `updated_at` bumped.
Fields not included in the request body are left untouched.

---

## Step 6 — Verify duplicate card creation is rejected

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST http://localhost:8000/models/$MODEL_ID/versions/$VERSION_ID/card \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"intended_use":"should be rejected"}'
```

Expected: `400` — one card per version. Use PUT to update an existing one.

---

## Step 7 — Link a dataset to the version (5C)

```bash
curl -s -X POST http://localhost:8000/models/$MODEL_ID/versions/$VERSION_ID/datasets \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"dataset_name":"invoices-q1-2026","dataset_hash":"sha256-abc123","role":"training","row_count":50000}' \
  | python3 -m json.tool
```

Expected:
```json
{
    "id": 1,
    "version_id": 5,
    "dataset_name": "invoices-q1-2026",
    "dataset_hash": "sha256-abc123",
    "dataset_uri": null,
    "role": "training",
    "row_count": 50000,
    "notes": null,
    "linked_by": "phase5tester",
    "created_at": "..."
}
```

Note the `id` in the response — that's `LINK_ID`, used in Step 9.

---

## Step 8 — List datasets linked to a version

```bash
curl -s http://localhost:8000/models/$MODEL_ID/versions/$VERSION_ID/datasets \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected: `total: 1`, the link from Step 7.

---

## Step 9 — Query lineage by dataset hash

Answers: "which model versions used this dataset?"

```bash
curl -s http://localhost:8000/lineage/dataset/sha256-abc123 \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected:
```json
{
    "dataset_hash": "sha256-abc123",
    "dataset_name": "invoices-q1-2026",
    "versions": [
        {
            "version_id": 5,
            "version": "1.0.0",
            "stage": "dev",
            "model_id": 15,
            "model_name": "phase5-test-model",
            "role": "training",
            "linked_by": "phase5tester",
            "created_at": "..."
        }
    ],
    "total": 1
}
```

A hash with no links returns `404`:
```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  http://localhost:8000/lineage/dataset/sha256-does-not-exist \
  -H "Authorization: Bearer $TOKEN"
```
Expected: `404`

---

## Step 10 — Query lineage by version id

Answers: "what data trained this specific version?"

```bash
curl -s http://localhost:8000/lineage/version/$VERSION_ID \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected: `total: 1`, the same dataset link.

---

## Step 11 — Delete the dataset link (admin only)

```bash
LINK_ID=1   # use the id from Step 7's response

curl -s -o /dev/null -w "%{http_code}\n" \
  -X DELETE http://localhost:8000/models/$MODEL_ID/versions/$VERSION_ID/datasets/$LINK_ID \
  -H "Authorization: Bearer $TOKEN"
```

Expected: `204`

Confirm removal:
```bash
curl -s http://localhost:8000/models/$MODEL_ID/versions/$VERSION_ID/datasets \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```
Expected: `total: 0`

---

## Step 12 — Signed download URL fallback (5A)

```bash
echo "test content" > /tmp/smoke_test.txt

ARTIFACT_ID=$(curl -s -X POST http://localhost:8000/models/$MODEL_ID/versions/$VERSION_ID/artifacts \
  -H "Authorization: Bearer $TOKEN" \
  -F "artifact_type=weights" -F "file=@/tmp/smoke_test.txt" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -i http://localhost:8000/models/$MODEL_ID/versions/$VERSION_ID/artifacts/$ARTIFACT_ID/download \
  -H "Authorization: Bearer $TOKEN" | head -20
```

Expected, depending on `STORAGE_BACKEND`:

- **`STORAGE_BACKEND=local`** → `200 OK`, file content streamed directly in
  the response body. `get_signed_url()` returns `None` for LocalStorage by
  design, so the endpoint falls back to the original Phase 1 streaming path.
- **`STORAGE_BACKEND=gcs`**, signing succeeds → `307 Temporary Redirect`
  with a `location:` header pointing at a `storage.googleapis.com` URL.
- **`STORAGE_BACKEND=gcs`**, signing fails (commonly: `gcloud auth
  application-default login` credentials lack a private key needed for V4
  signing) → `200 OK`, streamed fallback, identical to the local case. This
  is the intended behavior, not a bug — `get_signed_url()` is designed to
  never raise. Check server logs for a `WARNING` from `app/storage/gcs.py`
  if you want to confirm *why* it fell back.

Neither outcome is wrong by itself; what matters is that the response is
never a `500`.

---

## RBAC Summary

| Role | POST /card | PUT /card | DELETE /card | POST /datasets | DELETE /datasets/{id} |
|------|-----------|-----------|--------------|-----------------|------------------------|
| viewer | 403 | 403 | 403 | 403 | 403 |
| ml_engineer | 201 | 200 | 403 | 201 | 403 |
| admin | 201 | 200 | 204 | 201 | 204 |

GET endpoints (`/card`, `/datasets`, `/lineage/...`) are viewer+ for all
roles, matching the read-access pattern used everywhere else in the API.

---

## All Phase 5 endpoints verified

| Endpoint | Verified |
|----------|---------|
| `POST /models/{id}/versions/{vid}/card` | Yes |
| `GET /models/{id}/versions/{vid}/card` | Yes |
| `PUT /models/{id}/versions/{vid}/card` | Yes |
| `DELETE /models/{id}/versions/{vid}/card` | Yes |
| Duplicate card creation rejected (400) | Yes |
| `POST /models/{id}/versions/{vid}/datasets` | Yes |
| `GET /models/{id}/versions/{vid}/datasets` | Yes |
| `DELETE /models/{id}/versions/{vid}/datasets/{link_id}` | Yes |
| `GET /lineage/dataset/{hash}` | Yes |
| `GET /lineage/dataset/{hash}` with no matches (404) | Yes |
| `GET /lineage/version/{vid}` | Yes |
| Signed URL fallback on download | Yes |
| RBAC across all three roles | Yes |

Automated coverage: see `tests/test_api.py` (19 Phase 5 tests, appended
after the Phase 4 admin tests). Run with `pytest -v` — Phase 5 alone adds
no new dependencies beyond what Phases 1–4 already require.
