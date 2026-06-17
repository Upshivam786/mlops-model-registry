from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from pydantic import EmailStr


# ── Model Schemas ─────────────────────────────────────────────────────────────

class ModelBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    owner: Optional[str] = Field(None, max_length=255)
    tags: Optional[str] = Field(None, max_length=500)

class ModelCreate(ModelBase):
    pass

class ModelRead(ModelBase):
    id: int
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

class ModelUpdate(BaseModel):
    description: Optional[str] = None
    owner: Optional[str] = Field(None, max_length=255)
    tags: Optional[str] = Field(None, max_length=500)


# ── Model Version Schemas ─────────────────────────────────────────────────────

class ModelVersionBase(BaseModel):
    version: str = Field(..., max_length=50)
    stage: str = Field(default="dev", max_length=50)
    description: Optional[str] = None

class ModelVersionCreate(ModelVersionBase):
    pass

class ModelVersionRead(ModelVersionBase):
    id: int
    model_id: int
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

class ModelVersionUpdate(BaseModel):
    stage: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None


# ── Model Artifact Schemas ────────────────────────────────────────────────────

class ModelArtifactBase(BaseModel):
    artifact_type: str = Field(..., max_length=100)
    artifact_path: str = Field(..., max_length=500)
    file_size: Optional[int] = None
    checksum: Optional[str] = Field(None, max_length=255)

class ModelArtifactCreate(ModelArtifactBase):
    pass

class ModelArtifactRead(ModelArtifactBase):
    id: int
    version_id: int
    created_at: datetime
    class Config:
        from_attributes = True


# ── List / Paginated Response Schemas ─────────────────────────────────────────

class ModelList(BaseModel):
    models: List[ModelRead]
    total: int
    page: int
    size: int

class ModelVersionList(BaseModel):
    versions: List[ModelVersionRead]
    total: int
    page: int
    size: int

class ModelArtifactList(BaseModel):
    artifacts: List[ModelArtifactRead]
    total: int
    page: int
    size: int


# ── Auth Schemas ──────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserRead(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str
    is_active: bool
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class LoginRequest(BaseModel):
    username: str
    password: str


# ── Audit Log Schemas ─────────────────────────────────────────────────────────

class AuditLogRead(BaseModel):
    id: int
    user_id: int
    username: str
    action: str
    resource_type: str
    resource_id: int
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    timestamp: datetime
    class Config:
        from_attributes = True

class AuditLogList(BaseModel):
    logs: List[AuditLogRead]
    total: int
    page: int
    size: int


# ── Training Run Schemas (Phase 3) ────────────────────────────────────────────

class TrainingRunCreate(BaseModel):
    """
    Logged by the data scientist after training completes.
    All fields optional except metrics — at minimum log what you measured.
    """
    # Dataset
    dataset_name:      Optional[str]   = None
    dataset_hash:      Optional[str]   = None

    # Hyperparameters — pass full dict, key ones extracted automatically
    hyperparameters:   Optional[dict]  = None
    learning_rate:     Optional[float] = None
    epochs:            Optional[int]   = None
    batch_size:        Optional[int]   = None

    # Metrics — pass full dict, key ones extracted automatically
    metrics:           Optional[dict]  = None
    accuracy:          Optional[float] = Field(None, ge=0.0, le=1.0)
    f1_score:          Optional[float] = Field(None, ge=0.0, le=1.0)
    loss:              Optional[float] = None

    # Framework
    framework:         Optional[str]   = None
    framework_version: Optional[str]   = None

    # Duration in seconds
    training_duration: Optional[int]   = None


class TrainingRunRead(BaseModel):
    id:                int
    version_id:        int
    dataset_name:      Optional[str]
    dataset_hash:      Optional[str]
    hyperparameters:   Optional[str]   # stored as JSON string
    learning_rate:     Optional[float]
    epochs:            Optional[int]
    batch_size:        Optional[int]
    metrics:           Optional[str]   # stored as JSON string
    accuracy:          Optional[float]
    f1_score:          Optional[float]
    loss:              Optional[float]
    framework:         Optional[str]
    framework_version: Optional[str]
    training_duration: Optional[int]
    created_by:        str
    created_at:        datetime

    class Config:
        from_attributes = True


class ExperimentSummary(BaseModel):
    """
    Flattened view for comparing versions side by side.
    Returned by GET /experiments and GET /models/{id}/versions/compare
    """
    version_id:        int
    version:           str
    stage:             str
    model_id:          int
    model_name:        str
    accuracy:          Optional[float]
    f1_score:          Optional[float]
    loss:              Optional[float]
    learning_rate:     Optional[float]
    epochs:            Optional[int]
    batch_size:        Optional[int]
    dataset_name:      Optional[str]
    framework:         Optional[str]
    training_duration: Optional[int]
    created_by:        str
    created_at:        datetime

    class Config:
        from_attributes = True


class ExperimentList(BaseModel):
    experiments: List[ExperimentSummary]
    total: int
    page: int
    size: int
