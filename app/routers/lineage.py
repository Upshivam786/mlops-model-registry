from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app import models
from app.schemas import (
    DatasetLinkCreate, DatasetLinkRead, DatasetLinkList,
    DatasetLineage, LineageVersionSummary,
)
from app.dependencies import get_db
from app.auth.dependencies import get_current_user, require_admin, require_ml_engineer
from app.models import User, DatasetLink, ModelVersion, Model
from app.audit import write_audit_log

router = APIRouter(tags=["lineage"])


def _get_version_or_404(db: Session, model_id: int, version_id: int) -> ModelVersion:
    db_model = db.query(Model).filter(Model.id == model_id).first()
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")
    db_version = db.query(ModelVersion).filter(
        ModelVersion.id == version_id,
        ModelVersion.model_id == model_id
    ).first()
    if not db_version:
        raise HTTPException(status_code=404, detail="Model version not found")
    return db_version


# ── Link a dataset to a version ──────────────────────────────────────────────

@router.post(
    "/models/{model_id}/versions/{version_id}/datasets",
    response_model=DatasetLinkRead,
    status_code=status.HTTP_201_CREATED,
)
def link_dataset(
    model_id: int,
    version_id: int,
    link: DatasetLinkCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ml_engineer),
):
    """
    Record that a version was trained/validated/tested on a dataset.
    A version can have multiple dataset links (e.g. one 'training' role,
    one 'validation' role); duplicate (version_id, dataset_hash, role)
    combinations are allowed since re-linking with updated row_count/notes
    is a legitimate use case — this endpoint does not dedupe.
    """
    _get_version_or_404(db, model_id, version_id)

    db_link = DatasetLink(
        version_id=version_id,
        linked_by=current_user.username,
        **link.model_dump(),
    )
    db.add(db_link)
    db.flush()
    write_audit_log(
        db=db, user=current_user,
        action="CREATE", resource_type="dataset_link", resource_id=db_link.id,
        new_value={
            "version_id": version_id,
            "dataset_name": db_link.dataset_name,
            "dataset_hash": db_link.dataset_hash,
            "role": db_link.role,
        },
    )
    db.commit()
    db.refresh(db_link)
    return db_link


@router.get(
    "/models/{model_id}/versions/{version_id}/datasets",
    response_model=DatasetLinkList,
)
def list_version_datasets(
    model_id: int,
    version_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    role: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all datasets linked to a specific version."""
    _get_version_or_404(db, model_id, version_id)

    query = db.query(DatasetLink).filter(DatasetLink.version_id == version_id)
    if role:
        query = query.filter(DatasetLink.role == role)

    total = query.count()
    links = query.order_by(DatasetLink.created_at.desc()).offset((page - 1) * size).limit(size).all()
    return DatasetLinkList(links=links, total=total, page=page, size=size)


@router.delete(
    "/models/{model_id}/versions/{version_id}/datasets/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_dataset_link(
    model_id: int,
    version_id: int,
    link_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _get_version_or_404(db, model_id, version_id)

    db_link = db.query(DatasetLink).filter(
        DatasetLink.id == link_id,
        DatasetLink.version_id == version_id,
    ).first()
    if not db_link:
        raise HTTPException(status_code=404, detail="Dataset link not found")

    write_audit_log(
        db=db, user=current_user,
        action="DELETE", resource_type="dataset_link", resource_id=db_link.id,
        old_value={"dataset_hash": db_link.dataset_hash, "dataset_name": db_link.dataset_name},
    )
    db.delete(db_link)
    db.commit()
    return None


# ── Lineage queries ───────────────────────────────────────────────────────────
# These are intentionally registered with concrete prefixes ("/lineage/dataset"
# and "/lineage/version") rather than under /models, so there's no risk of the
# route-ordering int-parsing trap that affects /models/{id}/versions/compare.

@router.get(
    "/lineage/dataset/{dataset_hash}",
    response_model=DatasetLineage,
)
def get_dataset_lineage(
    dataset_hash: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Given a dataset hash, return every model version that used it.
    Answers: "if this dataset turns out to be biased / leaked / wrong,
    which models do I need to re-evaluate or pull from prod?"
    """
    rows = (
        db.query(DatasetLink, ModelVersion, Model)
        .join(ModelVersion, ModelVersion.id == DatasetLink.version_id)
        .join(Model, Model.id == ModelVersion.model_id)
        .filter(DatasetLink.dataset_hash == dataset_hash)
        .order_by(DatasetLink.created_at.desc())
        .all()
    )

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No model versions found using dataset hash '{dataset_hash}'"
        )

    dataset_name = rows[0][0].dataset_name

    versions = [
        LineageVersionSummary(
            version_id=version.id,
            version=version.version,
            stage=version.stage,
            model_id=model.id,
            model_name=model.name,
            role=link.role,
            linked_by=link.linked_by,
            created_at=link.created_at,
        )
        for link, version, model in rows
    ]

    return DatasetLineage(
        dataset_hash=dataset_hash,
        dataset_name=dataset_name,
        versions=versions,
        total=len(versions),
    )


@router.get(
    "/lineage/version/{version_id}",
    response_model=DatasetLinkList,
)
def get_version_lineage(
    version_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Given a version ID, return every dataset that fed into it.
    Answers: "what data was this specific model version trained/validated on?"
    Unlike list_version_datasets above, this doesn't require model_id in the
    path — useful when you only have a version_id (e.g. from /experiments).
    """
    db_version = db.query(ModelVersion).filter(ModelVersion.id == version_id).first()
    if not db_version:
        raise HTTPException(status_code=404, detail="Model version not found")

    query = db.query(DatasetLink).filter(DatasetLink.version_id == version_id)
    total = query.count()
    links = query.order_by(DatasetLink.created_at.desc()).offset((page - 1) * size).limit(size).all()
    return DatasetLinkList(links=links, total=total, page=page, size=size)
