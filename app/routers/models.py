from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import List, Optional
import math

from app import models
from app.schemas import ModelCreate, ModelRead, ModelUpdate, ModelList
from app.schemas import ModelVersionCreate, ModelVersionRead, ModelVersionList, ModelVersionUpdate
from app.schemas import ModelArtifactCreate, ModelArtifactRead, ModelArtifactList
from app.storage.base import StorageBase
from app.dependencies import get_db, get_storage
from app.auth.dependencies import get_current_user, require_admin, require_ml_engineer
from app.models import User
from app.audit import write_audit_log          # ← Phase 2

router = APIRouter(prefix="/models", tags=["models"])


# ── Models ────────────────────────────────────────────────────────────────────

@router.post("", response_model=ModelRead, status_code=status.HTTP_201_CREATED)
def create_model(
    model: ModelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ml_engineer),
):
    db_model = db.query(models.Model).filter(models.Model.name == model.name).first()
    if db_model:
        raise HTTPException(status_code=400, detail=f"Model with name '{model.name}' already exists")
    db_model = models.Model(**model.model_dump())
    db.add(db_model)
    db.flush()                                 # get db_model.id before commit
    write_audit_log(
        db=db, user=current_user,
        action="CREATE", resource_type="model", resource_id=db_model.id,
        new_value={"name": db_model.name, "owner": db_model.owner},
    )
    db.commit()
    db.refresh(db_model)
    return db_model


@router.get("", response_model=ModelList)
def list_models(
    page: int = 1,
    size: int = 10,
    name: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(models.Model)
    if name:
        query = query.filter(models.Model.name.contains(name))
    total = query.count()
    models_query = query.offset((page - 1) * size).limit(size).all()
    return ModelList(models=models_query, total=total, page=page, size=size)


@router.get("/{model_id}", response_model=ModelRead)
def get_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_model = db.query(models.Model).filter(models.Model.id == model_id).first()
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")
    return db_model


@router.put("/{model_id}", response_model=ModelRead)
def update_model(
    model_id: int,
    model_update: ModelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ml_engineer),
):
    db_model = db.query(models.Model).filter(models.Model.id == model_id).first()
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")
    old = {"description": db_model.description, "owner": db_model.owner, "tags": db_model.tags}
    update_data = model_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_model, field, value)
    write_audit_log(
        db=db, user=current_user,
        action="UPDATE", resource_type="model", resource_id=db_model.id,
        old_value=old, new_value=update_data,
    )
    db.commit()
    db.refresh(db_model)
    return db_model


@router.delete("/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model(
    model_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    db_model = db.query(models.Model).filter(models.Model.id == model_id).first()
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")
    write_audit_log(
        db=db, user=current_user,
        action="DELETE", resource_type="model", resource_id=db_model.id,
        old_value={"name": db_model.name},
    )
    db.delete(db_model)
    db.commit()
    return None


# ── Versions ──────────────────────────────────────────────────────────────────

@router.post("/{model_id}/versions", response_model=ModelVersionRead, status_code=status.HTTP_201_CREATED)
def create_model_version(
    model_id: int,
    version: ModelVersionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ml_engineer),
):
    db_model = db.query(models.Model).filter(models.Model.id == model_id).first()
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")
    existing_version = db.query(models.ModelVersion).filter(
        models.ModelVersion.model_id == model_id,
        models.ModelVersion.version == version.version
    ).first()
    if existing_version:
        raise HTTPException(status_code=400, detail=f"Version '{version.version}' already exists for model {model_id}")
    db_version = models.ModelVersion(model_id=model_id, **version.model_dump())
    db.add(db_version)
    db.flush()
    write_audit_log(
        db=db, user=current_user,
        action="CREATE", resource_type="model_version", resource_id=db_version.id,
        new_value={"model_id": model_id, "version": db_version.version, "stage": db_version.stage},
    )
    db.commit()
    db.refresh(db_version)
    return db_version


@router.get("/{model_id}/versions", response_model=ModelVersionList)
def list_model_versions(
    model_id: int,
    page: int = 1,
    size: int = 10,
    stage: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_model = db.query(models.Model).filter(models.Model.id == model_id).first()
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")
    query = db.query(models.ModelVersion).filter(models.ModelVersion.model_id == model_id)
    if stage:
        query = query.filter(models.ModelVersion.stage == stage)
    total = query.count()
    versions = query.offset((page - 1) * size).limit(size).all()
    return ModelVersionList(versions=versions, total=total, page=page, size=size)


@router.get("/{model_id}/versions/{version_id}", response_model=ModelVersionRead)
def get_model_version(
    model_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_version = db.query(models.ModelVersion).filter(
        models.ModelVersion.id == version_id,
        models.ModelVersion.model_id == model_id
    ).first()
    if not db_version:
        raise HTTPException(status_code=404, detail="Model version not found")
    return db_version


@router.put("/{model_id}/versions/{version_id}", response_model=ModelVersionRead)
def update_model_version(
    model_id: int,
    version_id: int,
    version_update: ModelVersionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ml_engineer),
):
    db_version = db.query(models.ModelVersion).filter(
        models.ModelVersion.id == version_id,
        models.ModelVersion.model_id == model_id
    ).first()
    if not db_version:
        raise HTTPException(status_code=404, detail="Model version not found")

    old_stage = db_version.stage
    update_data = version_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_version, field, value)

    # Detect stage promotion specifically — important for Phase 2 approval workflow
    new_stage = update_data.get("stage")
    action = "PROMOTE" if new_stage and new_stage != old_stage else "UPDATE"

    write_audit_log(
        db=db, user=current_user,
        action=action, resource_type="model_version", resource_id=db_version.id,
        old_value={"stage": old_stage},
        new_value=update_data,
    )
    db.commit()
    db.refresh(db_version)
    return db_version


@router.delete("/{model_id}/versions/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model_version(
    model_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    db_version = db.query(models.ModelVersion).filter(
        models.ModelVersion.id == version_id,
        models.ModelVersion.model_id == model_id
    ).first()
    if not db_version:
        raise HTTPException(status_code=404, detail="Model version not found")
    write_audit_log(
        db=db, user=current_user,
        action="DELETE", resource_type="model_version", resource_id=db_version.id,
        old_value={"version": db_version.version, "stage": db_version.stage},
    )
    db.delete(db_version)
    db.commit()
    return None


# ── Artifacts ─────────────────────────────────────────────────────────────────

@router.post("/{model_id}/versions/{version_id}/artifacts", response_model=ModelArtifactRead, status_code=status.HTTP_201_CREATED)
def upload_model_artifact(
    model_id: int,
    version_id: int,
    file: UploadFile = File(...),
    artifact_type: str = Form(...),
    db: Session = Depends(get_db),
    storage: StorageBase = Depends(get_storage),
    current_user: User = Depends(require_ml_engineer),
):
    db_model = db.query(models.Model).filter(models.Model.id == model_id).first()
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")
    db_version = db.query(models.ModelVersion).filter(
        models.ModelVersion.id == version_id,
        models.ModelVersion.model_id == model_id
    ).first()
    if not db_version:
        raise HTTPException(status_code=404, detail="Model version not found")
    storage_path = f"models/{model_id}/versions/{version_id}/artifacts/{file.filename}"
    file.file.seek(0)
    storage.save(file.file, storage_path)
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)
    db_artifact = models.ModelArtifact(
        version_id=version_id,
        artifact_type=artifact_type,
        artifact_path=storage_path,
        file_size=file_size
    )
    db.add(db_artifact)
    db.flush()
    write_audit_log(
        db=db, user=current_user,
        action="CREATE", resource_type="artifact", resource_id=db_artifact.id,
        new_value={"artifact_type": artifact_type, "path": storage_path, "size": file_size},
    )
    db.commit()
    db.refresh(db_artifact)
    return db_artifact


@router.get("/{model_id}/versions/{version_id}/artifacts", response_model=ModelArtifactList)
def list_model_artifacts(
    model_id: int,
    version_id: int,
    page: int = 1,
    size: int = 10,
    artifact_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_model = db.query(models.Model).filter(models.Model.id == model_id).first()
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")
    db_version = db.query(models.ModelVersion).filter(
        models.ModelVersion.id == version_id,
        models.ModelVersion.model_id == model_id
    ).first()
    if not db_version:
        raise HTTPException(status_code=404, detail="Model version not found")
    query = db.query(models.ModelArtifact).filter(models.ModelArtifact.version_id == version_id)
    if artifact_type:
        query = query.filter(models.ModelArtifact.artifact_type == artifact_type)
    total = query.count()
    artifacts = query.offset((page - 1) * size).limit(size).all()
    return ModelArtifactList(artifacts=artifacts, total=total, page=page, size=size)


@router.get("/{model_id}/versions/{version_id}/artifacts/{artifact_id}", response_model=ModelArtifactRead)
def get_model_artifact(
    model_id: int,
    version_id: int,
    artifact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_artifact = db.query(models.ModelArtifact).filter(
        models.ModelArtifact.id == artifact_id,
        models.ModelArtifact.version_id == version_id
    ).first()
    if not db_artifact:
        raise HTTPException(status_code=404, detail="Model artifact not found")
    db_version = db.query(models.ModelVersion).filter(
        models.ModelVersion.id == version_id,
        models.ModelVersion.model_id == model_id
    ).first()
    if not db_version:
        raise HTTPException(status_code=404, detail="Model version not found")
    return db_artifact


@router.delete("/{model_id}/versions/{version_id}/artifacts/{artifact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_model_artifact(
    model_id: int,
    version_id: int,
    artifact_id: int,
    db: Session = Depends(get_db),
    storage: StorageBase = Depends(get_storage),
    current_user: User = Depends(require_admin),
):
    db_artifact = db.query(models.ModelArtifact).filter(
        models.ModelArtifact.id == artifact_id,
        models.ModelArtifact.version_id == version_id
    ).first()
    if not db_artifact:
        raise HTTPException(status_code=404, detail="Model artifact not found")
    db_version = db.query(models.ModelVersion).filter(
        models.ModelVersion.id == version_id,
        models.ModelVersion.model_id == model_id
    ).first()
    if not db_version:
        raise HTTPException(status_code=404, detail="Model version not found")
    write_audit_log(
        db=db, user=current_user,
        action="DELETE", resource_type="artifact", resource_id=db_artifact.id,
        old_value={"path": db_artifact.artifact_path, "type": db_artifact.artifact_type},
    )
    storage.delete(db_artifact.artifact_path)
    db.delete(db_artifact)
    db.commit()
    return None


@router.get("/{model_id}/versions/{version_id}/artifacts/{artifact_id}/download")
def download_model_artifact(
    model_id: int,
    version_id: int,
    artifact_id: int,
    db: Session = Depends(get_db),
    storage: StorageBase = Depends(get_storage),
    current_user: User = Depends(get_current_user),
):
    db_artifact = db.query(models.ModelArtifact).filter(
        models.ModelArtifact.id == artifact_id,
        models.ModelArtifact.version_id == version_id
    ).first()
    if not db_artifact:
        raise HTTPException(status_code=404, detail="Model artifact not found")
    db_version = db.query(models.ModelVersion).filter(
        models.ModelVersion.id == version_id,
        models.ModelVersion.model_id == model_id
    ).first()
    if not db_version:
        raise HTTPException(status_code=404, detail="Model version not found")
    file_data = storage.load(db_artifact.artifact_path)
    content = file_data.read()
    file_data.close()
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={db_artifact.artifact_path.split('/')[-1]}"}
    )
