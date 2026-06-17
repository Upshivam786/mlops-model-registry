# Phase 3 — Experiment Tracking Testing Guide

## 1. Authenticate

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"yourusername","password":"yourpassword"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
```

---

## 2. Create Training Run

```bash
curl -s -X POST \
  http://localhost:8000/models/15/versions/5/training-run \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_name": "invoices-q1-2026",
    "dataset_hash": "sha256-abc123",
    "hyperparameters": {"lr": 0.001, "epochs": 50, "batch_size": 32},
    "metrics": {"accuracy": 0.94, "f1_score": 0.91, "loss": 0.12},
    "accuracy": 0.94,
    "f1_score": 0.91,
    "loss": 0.12,
    "framework": "pytorch",
    "framework_version": "2.1.0",
    "training_duration": 3600
  }' | python3 -m json.tool
```

Expected:

```json
{
  "version_id": 5,
  "accuracy": 0.94,
  "f1_score": 0.91
}
```

---

## 3. Get Training Run

```bash
curl -s \
  http://localhost:8000/models/15/versions/5/training-run \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -m json.tool
```

---

## 4. Compare Versions

```bash
curl -s \
  http://localhost:8000/models/15/versions/compare \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -m json.tool
```

---

## 5. Query By Accuracy

```bash
curl -s \
  "http://localhost:8000/experiments?min_accuracy=0.90" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -m json.tool
```

---

## 6. Query Production Experiments

```bash
curl -s \
  "http://localhost:8000/experiments?stage=prod&sort_by=f1_score&order=desc" \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -m json.tool
```

---

## Verification Checklist

* [x] Training run creation works
* [x] Training run retrieval works
* [x] Version comparison works
* [x] Accuracy filtering works
* [x] Stage filtering works
* [x] Sorting by metric works
* [x] JWT authentication enforced
* [x] Pagination supported

