from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models
from app.schemas import ModelCardCreate, ModelCardUpdate, ModelCardRead
from app.dependencies import get_db
from app.auth.dependencies import get_current_user, require_admin, require_ml_engineer
from app.models import User, ModelCard
from app.audit import write_audit_log

# Mounted under the same /models prefix as app/routers/models.py so the
# routes read naturally as /models/{model_id}/versions/{version_id}/card
router = APIRouter(prefix="/models", tags=["model-cards"])


def _get_version_or_404(db: Session, model_id: int, version_id: int) -> models.ModelVersion:
    db_model = db.query(models.Model).filter(models.Model.id == model_id).first()
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")
    db_version = db.query(models.ModelVersion).filter(
        models.ModelVersion.id == version_id,
        models.ModelVersion.model_id == model_id
    ).first()
    if not db_version:
        raise HTTPException(status_code=404, detail="Model version not found")
    return db_version


@router.post(
    "/{model_id}/versions/{version_id}/card",
    response_model=ModelCardRead,
    status_code=status.HTTP_201_CREATED,
)
def create_model_card(
    model_id: int,
    version_id: int,
    card: ModelCardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ml_engineer),
):
    """Create the model card for a version. One card per version — use PUT
    to update an existing one rather than POSTing again."""
    _get_version_or_404(db, model_id, version_id)

    existing = db.query(ModelCard).filter(ModelCard.version_id == version_id).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Model card already exists for version {version_id}. Use PUT to update it."
        )

    db_card = ModelCard(
        version_id=version_id,
        created_by=current_user.username,
        **card.model_dump(),
    )
    db.add(db_card)
    db.flush()
    write_audit_log(
        db=db, user=current_user,
        action="CREATE", resource_type="model_card", resource_id=db_card.id,
        new_value={"version_id": version_id},
    )
    db.commit()
    db.refresh(db_card)
    return db_card


@router.get(
    "/{model_id}/versions/{version_id}/card",
    response_model=ModelCardRead,
)
def get_model_card(
    model_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _get_version_or_404(db, model_id, version_id)

    db_card = db.query(ModelCard).filter(ModelCard.version_id == version_id).first()
    if not db_card:
        raise HTTPException(status_code=404, detail="Model card not found for this version")
    return db_card


@router.put(
    "/{model_id}/versions/{version_id}/card",
    response_model=ModelCardRead,
)
def update_model_card(
    model_id: int,
    version_id: int,
    card_update: ModelCardUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ml_engineer),
):
    _get_version_or_404(db, model_id, version_id)

    db_card = db.query(ModelCard).filter(ModelCard.version_id == version_id).first()
    if not db_card:
        raise HTTPException(status_code=404, detail="Model card not found for this version")

    update_data = card_update.model_dump(exclude_unset=True)
    old_value = {field: getattr(db_card, field) for field in update_data.keys()}

    for field, value in update_data.items():
        setattr(db_card, field, value)

    write_audit_log(
        db=db, user=current_user,
        action="UPDATE", resource_type="model_card", resource_id=db_card.id,
        old_value=old_value, new_value=update_data,
    )
    db.commit()
    db.refresh(db_card)
    return db_card


@router.delete(
    "/{model_id}/versions/{version_id}/card",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_model_card(
    model_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _get_version_or_404(db, model_id, version_id)

    db_card = db.query(ModelCard).filter(ModelCard.version_id == version_id).first()
    if not db_card:
        raise HTTPException(status_code=404, detail="Model card not found for this version")

    write_audit_log(
        db=db, user=current_user,
        action="DELETE", resource_type="model_card", resource_id=db_card.id,
        old_value={"version_id": version_id},
    )
    db.delete(db_card)
    db.commit()
    return None
