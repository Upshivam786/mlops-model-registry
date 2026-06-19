"""
kimchi_sdk/client.py

Python SDK for the Kimchi MLOps Model Registry.

Usage:
    from kimchi_sdk import ModelRegistry

    registry = ModelRegistry("http://localhost:8000")
    registry.login("shivam", "secret123")

    # Register a model
    model = registry.create_model("procurement-classifier", owner="shivam")

    # Create a version
    version = registry.create_version(model["id"], "1.0.0", stage="dev")

    # Upload a file
    registry.upload_artifact(model["id"], version["id"], "/path/to/model.pkl", artifact_type="weights")

    # Log training metrics
    registry.log_run(
        model["id"], version["id"],
        accuracy=0.94, f1_score=0.91, loss=0.12,
        hyperparameters={"lr": 0.001, "epochs": 50},
        dataset_name="invoices-q1-2026",
        framework="pytorch",
    )

    # Promote to production
    registry.promote(model["id"], version["id"], stage="prod")

    # Find best model in prod
    best = registry.get_best_experiment(stage="prod", sort_by="accuracy")
    print(best)
"""

import os
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    raise ImportError("kimchi_sdk requires 'requests'. Install with: pip install requests")


class ModelRegistryError(Exception):
    """Raised when the registry API returns an error."""
    pass


class ModelRegistry:
    """
    Client for the Kimchi MLOps Model Registry API.

    Args:
        base_url: Registry API base URL. Default: http://localhost:8000
        token:    Optional JWT access token. Can also call .login() after init.
    """

    def __init__(self, base_url: str = "http://localhost:8000", token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._refresh_token = None

    # ── Auth ──────────────────────────────────────────────────────────────────

    def login(self, username: str, password: str) -> dict:
        """Login and store access + refresh tokens."""
        resp = requests.post(
            f"{self.base_url}/auth/login",
            json={"username": username, "password": password},
        )
        self._raise_for_status(resp)
        data = resp.json()
        self._token        = data["access_token"]
        self._refresh_token = data.get("refresh_token")
        return data

    def refresh(self) -> dict:
        """Exchange refresh token for new access token."""
        if not self._refresh_token:
            raise ModelRegistryError("No refresh token available. Call .login() first.")
        resp = requests.post(
            f"{self.base_url}/auth/refresh",
            params={"refresh_token": self._refresh_token},
        )
        self._raise_for_status(resp)
        data = resp.json()
        self._token         = data["access_token"]
        self._refresh_token  = data.get("refresh_token")
        return data

    # ── Models ────────────────────────────────────────────────────────────────

    def create_model(
        self,
        name: str,
        description: Optional[str] = None,
        owner: Optional[str] = None,
        tags: Optional[str] = None,
    ) -> dict:
        """Register a new model. Returns the created model dict."""
        resp = self._post("/models", json={
            "name": name,
            "description": description,
            "owner": owner,
            "tags": tags,
        })
        return resp

    def get_model(self, model_id: int) -> dict:
        """Get a model by ID."""
        return self._get(f"/models/{model_id}")

    def list_models(self, name: Optional[str] = None, page: int = 1, size: int = 10) -> dict:
        """List models with optional name filter."""
        params = {"page": page, "size": size}
        if name:
            params["name"] = name
        return self._get("/models", params=params)

    def update_model(self, model_id: int, **kwargs) -> dict:
        """Update model metadata (description, owner, tags)."""
        return self._put(f"/models/{model_id}", json=kwargs)

    def delete_model(self, model_id: int) -> None:
        """Delete a model and all its versions. Admin only."""
        self._delete(f"/models/{model_id}")

    # ── Versions ──────────────────────────────────────────────────────────────

    def create_version(
        self,
        model_id: int,
        version: str,
        stage: str = "dev",
        description: Optional[str] = None,
    ) -> dict:
        """Create a new version for a model."""
        return self._post(f"/models/{model_id}/versions", json={
            "version": version,
            "stage": stage,
            "description": description,
        })

    def get_version(self, model_id: int, version_id: int) -> dict:
        """Get a specific version."""
        return self._get(f"/models/{model_id}/versions/{version_id}")

    def list_versions(self, model_id: int, stage: Optional[str] = None) -> dict:
        """List all versions of a model, optionally filtered by stage."""
        params = {}
        if stage:
            params["stage"] = stage
        return self._get(f"/models/{model_id}/versions", params=params)

    def promote(self, model_id: int, version_id: int, stage: str) -> dict:
        """
        Promote a version to a new stage.

        Stages: dev → staging → prod → archived

        Example:
            registry.promote(model_id, version_id, stage="prod")
        """
        return self._put(f"/models/{model_id}/versions/{version_id}", json={"stage": stage})

    def compare_versions(self, model_id: int) -> dict:
        """Compare all versions of a model with their metrics side by side."""
        return self._get(f"/models/{model_id}/versions/compare")

    # ── Artifacts ─────────────────────────────────────────────────────────────

    def upload_artifact(
        self,
        model_id: int,
        version_id: int,
        file_path: str,
        artifact_type: str = "weights",
    ) -> dict:
        """
        Upload a local file as an artifact.

        Args:
            file_path:     Local path to the file to upload
            artifact_type: Type label — weights | config | metrics | tokenizer | schema
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(path, "rb") as f:
            resp = requests.post(
                f"{self.base_url}/models/{model_id}/versions/{version_id}/artifacts",
                files={"file": (path.name, f, "application/octet-stream")},
                data={"artifact_type": artifact_type},
                headers=self._headers(),
            )
        self._raise_for_status(resp)
        return resp.json()

    def download_artifact(
        self,
        model_id: int,
        version_id: int,
        artifact_id: int,
        save_path: str,
    ) -> str:
        """
        Download an artifact to a local file.

        Returns the path where the file was saved.
        """
        resp = requests.get(
            f"{self.base_url}/models/{model_id}/versions/{version_id}/artifacts/{artifact_id}/download",
            headers=self._headers(),
        )
        self._raise_for_status(resp)
        with open(save_path, "wb") as f:
            f.write(resp.content)
        return save_path

    def list_artifacts(self, model_id: int, version_id: int) -> dict:
        """List all artifacts for a version."""
        return self._get(f"/models/{model_id}/versions/{version_id}/artifacts")

    # ── Experiment tracking ───────────────────────────────────────────────────

    def log_run(
        self,
        model_id: int,
        version_id: int,
        accuracy: Optional[float] = None,
        f1_score: Optional[float] = None,
        loss: Optional[float] = None,
        hyperparameters: Optional[dict] = None,
        dataset_name: Optional[str] = None,
        dataset_hash: Optional[str] = None,
        framework: Optional[str] = None,
        framework_version: Optional[str] = None,
        training_duration: Optional[int] = None,
    ) -> dict:
        """
        Log a training run for a model version.

        Example:
            registry.log_run(
                model_id, version_id,
                accuracy=0.94,
                f1_score=0.91,
                loss=0.12,
                hyperparameters={"lr": 0.001, "epochs": 50, "batch_size": 32},
                dataset_name="invoices-q1-2026",
                framework="pytorch",
                training_duration=3600,
            )
        """
        return self._post(
            f"/models/{model_id}/versions/{version_id}/training-run",
            json={
                "accuracy":          accuracy,
                "f1_score":          f1_score,
                "loss":              loss,
                "hyperparameters":   hyperparameters,
                "dataset_name":      dataset_name,
                "dataset_hash":      dataset_hash,
                "framework":         framework,
                "framework_version": framework_version,
                "training_duration": training_duration,
            },
        )

    def get_run(self, model_id: int, version_id: int) -> dict:
        """Get the training run for a specific version."""
        return self._get(f"/models/{model_id}/versions/{version_id}/training-run")

    def get_experiments(
        self,
        min_accuracy: Optional[float] = None,
        min_f1: Optional[float] = None,
        max_loss: Optional[float] = None,
        stage: Optional[str] = None,
        framework: Optional[str] = None,
        dataset_name: Optional[str] = None,
        sort_by: str = "accuracy",
        order: str = "desc",
        page: int = 1,
        size: int = 50,
    ) -> dict:
        """
        Query training runs across all models.

        Example:
            # Best models in production
            best = registry.get_experiments(stage="prod", sort_by="accuracy")

            # All pytorch models with F1 > 0.85
            results = registry.get_experiments(framework="pytorch", min_f1=0.85)
        """
        params = {k: v for k, v in {
            "min_accuracy": min_accuracy,
            "min_f1":       min_f1,
            "max_loss":     max_loss,
            "stage":        stage,
            "framework":    framework,
            "dataset_name": dataset_name,
            "sort_by":      sort_by,
            "order":        order,
            "page":         page,
            "size":         size,
        }.items() if v is not None}
        return self._get("/experiments", params=params)

    def get_best_experiment(self, stage: Optional[str] = None, sort_by: str = "accuracy") -> Optional[dict]:
        """
        Return the single best experiment by a metric.

        Example:
            best = registry.get_best_experiment(stage="prod")
            print(f"Best model: {best['model_name']} v{best['version']} acc={best['accuracy']}")
        """
        results = self.get_experiments(stage=stage, sort_by=sort_by, order="desc", size=1)
        experiments = results.get("experiments", [])
        return experiments[0] if experiments else None

    # ── Audit logs ────────────────────────────────────────────────────────────

    def get_audit_logs(
        self,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        username: Optional[str] = None,
        page: int = 1,
        size: int = 50,
    ) -> dict:
        """Get audit logs. Admin only."""
        params = {k: v for k, v in {
            "action":        action,
            "resource_type": resource_type,
            "username":      username,
            "page":          page,
            "size":          size,
        }.items() if v is not None}
        return self._get("/audit-logs", params=params)

    # ── Admin ─────────────────────────────────────────────────────────────────

    def list_users(self) -> dict:
        """List all users. Admin only."""
        return self._get("/admin/users")

    def set_role(self, user_id: int, role: str) -> dict:
        """Promote or demote a user. Admin only."""
        return self._put(f"/admin/users/{user_id}/role", json={"role": role})

    def deactivate_user(self, user_id: int) -> dict:
        """Deactivate a user account. Admin only."""
        return self._delete_with_response(f"/admin/users/{user_id}")

    # ── Internal HTTP helpers ─────────────────────────────────────────────────

    def _headers(self) -> dict:
        if not self._token:
            raise ModelRegistryError("Not authenticated. Call .login() first.")
        return {"Authorization": f"Bearer {self._token}"}

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        resp = requests.get(f"{self.base_url}{path}", headers=self._headers(), params=params)
        self._raise_for_status(resp)
        return resp.json()

    def _post(self, path: str, json: dict) -> dict:
        resp = requests.post(f"{self.base_url}{path}", headers=self._headers(), json=json)
        self._raise_for_status(resp)
        return resp.json()

    def _put(self, path: str, json: dict) -> dict:
        resp = requests.put(f"{self.base_url}{path}", headers=self._headers(), json=json)
        self._raise_for_status(resp)
        return resp.json()

    def _delete(self, path: str) -> None:
        resp = requests.delete(f"{self.base_url}{path}", headers=self._headers())
        self._raise_for_status(resp)

    def _delete_with_response(self, path: str) -> dict:
        resp = requests.delete(f"{self.base_url}{path}", headers=self._headers())
        self._raise_for_status(resp)
        return resp.json()

    def _raise_for_status(self, resp) -> None:
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise ModelRegistryError(f"HTTP {resp.status_code}: {detail}")
