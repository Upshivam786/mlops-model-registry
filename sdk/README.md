# kimchi-sdk

Python SDK for the [Kimchi MLOps Model Registry](https://github.com/Upshivam786/mlops-model-registry).

## Install

```bash
pip install requests
pip install -e ./sdk   # from project root
```

## Quickstart

```python
from kimchi_sdk import ModelRegistry

registry = ModelRegistry("http://localhost:8000")
registry.login("shivam", "secret123")

# Register a model
model = registry.create_model(
    "procurement-classifier",
    description="Classifies procurement documents",
    owner="shivam",
    tags="procurement,classification",
)

# Create a version
version = registry.create_version(model["id"], "1.0.0", stage="dev")

# Upload model file
registry.upload_artifact(
    model["id"], version["id"],
    file_path="model.pkl",
    artifact_type="weights",
)

# Log training metrics
registry.log_run(
    model["id"], version["id"],
    accuracy=0.94,
    f1_score=0.91,
    loss=0.12,
    hyperparameters={"lr": 0.001, "epochs": 50, "batch_size": 32},
    dataset_name="invoices-q1-2026",
    framework="pytorch",
    training_duration=3600,
)

# Promote to production
registry.promote(model["id"], version["id"], stage="prod")

# Find the best model in prod
best = registry.get_best_experiment(stage="prod", sort_by="accuracy")
print(f"Best: {best['model_name']} v{best['version']} accuracy={best['accuracy']}")

# Download a model
registry.download_artifact(model["id"], version["id"], artifact_id=1, save_path="retrieved_model.pkl")
```

## All Methods

| Method | Description |
|--------|-------------|
| `login(username, password)` | Authenticate and store tokens |
| `refresh()` | Refresh access token |
| `create_model(name, ...)` | Register a new model |
| `get_model(model_id)` | Get model by ID |
| `list_models(name, page, size)` | List models |
| `update_model(model_id, **kwargs)` | Update model metadata |
| `delete_model(model_id)` | Delete model (admin) |
| `create_version(model_id, version, stage)` | Create model version |
| `promote(model_id, version_id, stage)` | Change version stage |
| `compare_versions(model_id)` | Compare versions with metrics |
| `upload_artifact(model_id, version_id, file_path, artifact_type)` | Upload file |
| `download_artifact(model_id, version_id, artifact_id, save_path)` | Download file |
| `log_run(model_id, version_id, accuracy, f1_score, ...)` | Log training metrics |
| `get_experiments(stage, min_accuracy, sort_by, ...)` | Query experiments |
| `get_best_experiment(stage, sort_by)` | Get top experiment |
| `get_audit_logs(action, username, ...)` | Read audit log (admin) |
| `list_users()` | List all users (admin) |
| `set_role(user_id, role)` | Change user role (admin) |
| `deactivate_user(user_id)` | Deactivate user (admin) |
