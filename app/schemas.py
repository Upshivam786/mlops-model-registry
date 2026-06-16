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
    token_type: str

class LoginRequest(BaseModel):
    username: str
    password: str


# ── Audit Log Schemas (Phase 2) ───────────────────────────────────────────────

class AuditLogRead(BaseModel):
    id: int
    user_id: int
    username: str
    action: str           # CREATE | UPDATE | DELETE | PROMOTE
    resource_type: str    # model | model_version | artifact
    resource_id: int
    old_value: Optional[str] = None   # JSON string
    new_value: Optional[str] = None   # JSON string
    timestamp: datetime

    class Config:
        from_attributes = True

class AuditLogList(BaseModel):
    logs: List[AuditLogRead]
    total: int
    page: int
    size: int
