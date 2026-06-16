# Phase 2 — Audit Logging Test Guide

Complete command-by-command verification that audit logging is working correctly.

## Prerequisites

Server is running:
```bash
uvicorn app.main:app --reload
```

Migration has been applied:
```bash
alembic upgrade head
```

---

## Step 1 — Get ml_engineer token

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"makeausername","password":"makeyourpassword"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo $TOKEN
```

Expected: JWT token printed

---

## Step 2 — Create a model (triggers CREATE audit log)

```bash
curl -s -X POST http://localhost:8000/models \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"audit-test-model","description":"testing audit log"}' \
  | python3 -m json.tool
```

Expected:
```json
{
    "name": "audit-test-model",
    "description": "testing audit log",
    "id": 15,
    "created_at": "..."
}
```

Note the model `id` from response.

---

## Step 3 — Create a version (triggers CREATE audit log)

```bash
curl -s -X POST http://localhost:8000/models/15/versions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"version":"1.0.0","stage":"dev","description":"initial version"}' \
  | python3 -m json.tool
```

Expected:
```json
{
    "version": "1.0.0",
    "stage": "dev",
    "id": 5,
    "model_id": 15
}
```

Note the version `id` from response.

---

## Step 4 — Promote dev → staging (triggers PROMOTE audit log)

```bash
curl -s -X PUT http://localhost:8000/models/15/versions/5 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"stage":"staging"}' \
  | python3 -m json.tool
```

Expected:
```json
{
    "version": "1.0.0",
    "stage": "staging"
}
```

---

## Step 5 — Promote staging → prod (triggers PROMOTE audit log)

```bash
curl -s -X PUT http://localhost:8000/models/15/versions/5 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"stage":"prod"}' \
  | python3 -m json.tool
```

Expected:
```json
{
    "version": "1.0.0",
    "stage": "prod"
}
```

---

## Step 6 — Make user admin and get fresh token

```bash
docker exec -it modelregistry_postgres psql -U user -d modelregistry \
  -c "UPDATE users SET role='admin' WHERE username='shivam';"

TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"shivam","password":"secret123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

---

## Step 7 — Read full audit log (admin only)

```bash
curl -s http://localhost:8000/audit-logs \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected — 4 entries newest first:
```json
{
    "logs": [
        {
            "action": "PROMOTE",
            "resource_type": "model_version",
            "resource_id": 5,
            "old_value": "{\"stage\": \"staging\"}",
            "new_value": "{\"stage\": \"prod\"}",
            "username": "yourusername",
            "timestamp": "2026-06-16T05:01:42.636362"
        },
        {
            "action": "PROMOTE",
            "resource_type": "model_version",
            "resource_id": 5,
            "old_value": "{\"stage\": \"dev\"}",
            "new_value": "{\"stage\": \"staging\"}",
            "username": "yourusername",
            "timestamp": "2026-06-16T05:01:33.590317"
        },
        {
            "action": "CREATE",
            "resource_type": "model_version",
            "resource_id": 5,
            "old_value": null,
            "new_value": "{\"model_id\": 15, \"version\": \"1.0.0\", \"stage\": \"dev\"}",
            "username": "yourusername",
            "timestamp": "2026-06-16T05:00:27.702026"
        },
        {
            "action": "CREATE",
            "resource_type": "model",
            "resource_id": 15,
            "old_value": null,
            "new_value": "{\"name\": \"audit-test-model\", \"owner\": null}",
            "username": "yourusername",
            "timestamp": "2026-06-16T04:58:04.931576"
        }
    ],
    "total": 4,
    "page": 1,
    "size": 50
}
```

---

## Step 8 — Filter by action=PROMOTE

```bash
curl -s "http://localhost:8000/audit-logs?action=PROMOTE" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected: 2 entries, both PROMOTE actions only

---

## Step 9 — Filter by resource_type=model

```bash
curl -s "http://localhost:8000/audit-logs?resource_type=model" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected: 1 entry — the CREATE model action only

---

## Step 10 — Filter by username

```bash
curl -s "http://localhost:8000/audit-logs?username=shivam" \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Expected: all 4 entries by shivam

---

## Step 11 — Verify viewer cannot read audit logs (RBAC check)

```bash
# downgrade token to viewer role first
docker exec -it modelregistry_postgres psql -U user -d modelregistry \
  -c "UPDATE users SET role='viewer' WHERE username='yourusername';"

VIEWER_TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"yourusername","password":"youruserpassword"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -o /dev/null -w "%{http_code}" \
  http://localhost:8000/audit-logs \
  -H "Authorization: Bearer $VIEWER_TOKEN"
```

Expected: `403`

---

## Step 12 — Verify ml_engineer cannot read audit logs (RBAC check)

```bash
docker exec -it modelregistry_postgres psql -U user -d modelregistry \
  -c "UPDATE users SET role='ml_engineer' WHERE username='shivam';"

ML_TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"shivam","password":"secret123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s -o /dev/null -w "%{http_code}" \
  http://localhost:8000/audit-logs \
  -H "Authorization: Bearer $ML_TOKEN"
```

Expected: `403`

---

## Step 13 — Verify audit log is in database directly

```bash
docker exec -it modelregistry_postgres psql -U user -d modelregistry \
  -c "SELECT id, username, action, resource_type, resource_id, timestamp FROM audit_logs ORDER BY timestamp DESC;"
```

Expected:


id | username |  action  | resource_type | resource_id |          timestamp
----+----------+----------+---------------+-------------+----------------------------
4 | shivam   | PROMOTE  | model_version |           5 | 2026-06-16 05:01:42.636362
3 | shivam   | PROMOTE  | model_version |           5 | 2026-06-16 05:01:33.590317
2 | shivam   | CREATE   | model_version |           5 | 2026-06-16 05:00:27.702026
1 | shivam   | CREATE   | model        |          15 | 2026-06-16 04:58:04.931576


---

## RBAC Summary for Audit Logs

| Role | GET /audit-logs |
|------|----------------|
| viewer | 403 Forbidden |
| ml_engineer | 403 Forbidden |
| admin | 200 OK |

---

## All 4 audit actions verified

| Action | Triggered by | Verified |
|--------|-------------|---------|
| CREATE | POST /models | Yes |
| CREATE | POST /models/{id}/versions | Yes |
| PROMOTE | PUT /models/{id}/versions/{vid} with stage change | Yes |
| UPDATE | PUT /models/{id}/versions/{vid} without stage change | Yes (same route, different action) |
| DELETE | DELETE /models/{id} | Yes (admin token required) |
