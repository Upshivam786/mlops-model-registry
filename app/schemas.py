from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from pydantic import EmailStr

# Model Schemas
class ModelBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    owner: Optional[str] = Field(None, max_length=255)
    tags: Optional[str] = Field(None, max_length=500)  # Comma-separated tags

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

# Model Version Schemas
class ModelVersionBase(BaseModel):
    version: str = Field(..., max_length=50)
    stage: str = Field(default="dev", max_length=50)  # dev, staging, prod, archived
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

# Model Artifact Schemas
class ModelArtifactBase(BaseModel):
    artifact_type: str = Field(..., max_length=100)  # weights, config, metrics, etc.
    artifact_path: str = Field(..., max_length=500)
    file_size: Optional[int] = None  # Size in bytes
    checksum: Optional[str] = Field(None, max_length=255)  # SHA256 or similar

class ModelArtifactCreate(ModelArtifactBase):
    pass

class ModelArtifactRead(ModelArtifactBase):
    id: int
    version_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Response models for lists
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
