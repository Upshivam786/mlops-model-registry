from pydantic import BaseModel, Field
from typing import Optional, List
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
    refresh_token: Optional[str] = None   # ← Phase 4D: returned on login
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


# ── Training Run Schemas ──────────────────────────────────────────────────────

class TrainingRunCreate(BaseModel):
    dataset_name:      Optional[str]   = None
    dataset_hash:      Optional[str]   = None
    hyperparameters:   Optional[dict]  = None
    learning_rate:     Optional[float] = None
    epochs:            Optional[int]   = None
    batch_size:        Optional[int]   = None
    metrics:           Optional[dict]  = None
    accuracy:          Optional[float] = Field(None, ge=0.0, le=1.0)
    f1_score:          Optional[float] = Field(None, ge=0.0, le=1.0)
    loss:              Optional[float] = None
    framework:         Optional[str]   = None
    framework_version: Optional[str]   = None
    training_duration: Optional[int]   = None

class TrainingRunRead(BaseModel):
    id:                int
    version_id:        int
    dataset_name:      Optional[str]
    dataset_hash:      Optional[str]
    hyperparameters:   Optional[str]
    learning_rate:     Optional[float]
    epochs:            Optional[int]
    batch_size:        Optional[int]
    metrics:           Optional[str]
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


# ── Model Card Schemas ────────────────────────────────────────────────────────  ← Phase 5B

class ModelCardCreate(BaseModel):
    intended_use:                Optional[str] = None
    limitations:                 Optional[str] = None
    ethical_considerations:      Optional[str] = None
    training_data_summary:       Optional[str] = None
    evaluation_summary:          Optional[str] = None
    caveats_and_recommendations: Optional[str] = None

class ModelCardUpdate(BaseModel):
    intended_use:                Optional[str] = None
    limitations:                 Optional[str] = None
    ethical_considerations:      Optional[str] = None
    training_data_summary:       Optional[str] = None
    evaluation_summary:          Optional[str] = None
    caveats_and_recommendations: Optional[str] = None

class ModelCardRead(BaseModel):
    id:                          int
    version_id:                 int
    intended_use:                Optional[str]
    limitations:                 Optional[str]
    ethical_considerations:      Optional[str]
    training_data_summary:       Optional[str]
    evaluation_summary:          Optional[str]
    caveats_and_recommendations: Optional[str]
    created_by:                 str
    created_at:                 datetime
    updated_at:                 datetime
    class Config:
        from_attributes = True


# ── Data Lineage Schemas ──────────────────────────────────────────────────────  ← Phase 5C

class DatasetLinkCreate(BaseModel):
    dataset_name: str = Field(..., max_length=255)
    dataset_hash: str = Field(..., max_length=255)
    dataset_uri:  Optional[str] = Field(None, max_length=500)
    role:         str = Field(default="training", max_length=50)
    row_count:    Optional[int] = None
    notes:        Optional[str] = None

class DatasetLinkRead(BaseModel):
    id:            int
    version_id:    int
    dataset_name:  str
    dataset_hash:  str
    dataset_uri:   Optional[str]
    role:          str
    row_count:     Optional[int]
    notes:         Optional[str]
    linked_by:     str
    created_at:    datetime
    class Config:
        from_attributes = True

class DatasetLinkList(BaseModel):
    links: List[DatasetLinkRead]
    total: int
    page: int
    size: int

class LineageVersionSummary(BaseModel):
    """One model version that used a given dataset — returned by the
    dataset-centric lineage query (GET /lineage/dataset/{hash})."""
    version_id:   int
    version:      str
    stage:        str
    model_id:     int
    model_name:   str
    role:         str
    linked_by:    str
    created_at:   datetime
    class Config:
        from_attributes = True

class DatasetLineage(BaseModel):
    """Full lineage view for a dataset hash: every model version that
    consumed it, across the whole registry."""
    dataset_hash: str
    dataset_name: Optional[str] = None
    versions:     List[LineageVersionSummary]
    total:        int
