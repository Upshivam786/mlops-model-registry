"""
app/routers/experiments.py

Phase 3 — Experiment Tracking

Endpoints:
  POST /models/{model_id}/versions/{version_id}/training-run
       → log a training run for a version (ml_engineer+)

  GET  /models/{model_id}/versions/compare
       → compare all versions of a model side by side (viewer+)
       → MUST be registered before /{version_id}/training-run

  GET  /models/{model_id}/versions/{version_id}/training-run
       → get training run for a specific version (viewer+)

  GET  /experiments
       → query across ALL models by metric, stage, framework (viewer+)
       → supports: ?min_accuracy=0.90 ?min_f1=0.85 ?stage=prod ?framework=pytorch
       → supports: ?sort_by=accuracy&order=desc
"""

import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.auth.dependencies import get_current_user, require_ml_engineer
from app.models import Model, ModelVersion, TrainingRun, User
from app.schemas import (
    TrainingRunCreate,
    TrainingRunRead,
    ExperimentSummary,
    ExperimentList,
)
from app.audit import write_audit_log

router = APIRouter(tags=["experiments"])


# ── Log a training run ────────────────────────────────────────────────────────

@router.post(
    "/models/{model_id}/versions/{version_id}/training-run",
    response_model=TrainingRunRead,
    status_code=status.HTTP_201_CREATED,
)
def log_training_run(
    model_id: int,
    version_id: int,
    run_in: TrainingRunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ml_engineer),
):
    """
    Log hyperparameters and metrics for a model version after training.
    One training run per version — calling again overwrites the existing one.
    """
    db_version = db.query(ModelVersion).filter(
        ModelVersion.id == version_id,
        ModelVersion.model_id == model_id,
    ).first()
    if not db_version:
        raise HTTPException(status_code=404, detail="Model version not found")

    # One run per version — delete existing if present
    existing = db.query(TrainingRun).filter(TrainingRun.version_id == version_id).first()
    if existing:
        db.delete(existing)
        db.flush()

    # Extract key hyperparameters from the dict if not passed individually
    hp = run_in.hyperparameters or {}
    lr         = run_in.learning_rate or hp.get("learning_rate") or hp.get("lr")
    epochs     = run_in.epochs        or hp.get("epochs")
    batch_size = run_in.batch_size    or hp.get("batch_size")

    # Extract key metrics from the dict if not passed individually
    mt       = run_in.metrics or {}
    accuracy = run_in.accuracy or mt.get("accuracy")
    f1_score = run_in.f1_score or mt.get("f1_score") or mt.get("f1")
    loss     = run_in.loss     or mt.get("loss")

    db_run = TrainingRun(
        version_id        = version_id,
        dataset_name      = run_in.dataset_name,
        dataset_hash      = run_in.dataset_hash,
        hyperparameters   = json.dumps(run_in.hyperparameters) if run_in.hyperparameters else None,
        learning_rate     = lr,
        epochs            = epochs,
        batch_size        = batch_size,
        metrics           = json.dumps(run_in.metrics) if run_in.metrics else None,
        accuracy          = accuracy,
        f1_score          = f1_score,
        loss              = loss,
        framework         = run_in.framework,
        framework_version = run_in.framework_version,
        training_duration = run_in.training_duration,
        created_by        = current_user.username,
    )
    db.add(db_run)
    db.flush()

    write_audit_log(
        db=db, user=current_user,
        action="CREATE", resource_type="training_run", resource_id=db_run.id,
        new_value={
            "version_id": version_id,
            "accuracy":   accuracy,
            "f1_score":   f1_score,
            "dataset":    run_in.dataset_name,
        },
    )

    db.commit()
    db.refresh(db_run)
    return db_run


# ── Compare versions of a model ───────────────────────────────────────────────
# IMPORTANT: this route must stay ABOVE /{version_id}/training-run
# because FastAPI matches routes top-to-bottom and "compare" would
# otherwise be parsed as a {version_id} integer and fail.

@router.get(
    "/models/{model_id}/versions/compare",
    response_model=ExperimentList,
)
def compare_versions(
    model_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return all versions of a model with their training metrics side by side.
    Sorted by accuracy descending so the best version is always first.
    """
    db_model = db.query(Model).filter(Model.id == model_id).first()
    if not db_model:
        raise HTTPException(status_code=404, detail="Model not found")

    rows = (
        db.query(ModelVersion, TrainingRun)
        .outerjoin(TrainingRun, TrainingRun.version_id == ModelVersion.id)
        .filter(ModelVersion.model_id == model_id)
        .order_by(TrainingRun.accuracy.desc().nullslast())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    total = db.query(ModelVersion).filter(ModelVersion.model_id == model_id).count()

    results = []
    for version, run in rows:
        results.append(ExperimentSummary(
            version_id        = version.id,
            version           = version.version,
            stage             = version.stage,
            model_id          = model_id,
            model_name        = db_model.name,
            accuracy          = run.accuracy          if run else None,
            f1_score          = run.f1_score          if run else None,
            loss              = run.loss              if run else None,
            learning_rate     = run.learning_rate     if run else None,
            epochs            = run.epochs            if run else None,
            batch_size        = run.batch_size        if run else None,
            dataset_name      = run.dataset_name      if run else None,
            framework         = run.framework         if run else None,
            training_duration = run.training_duration if run else None,
            created_by        = run.created_by        if run else version.version,
            created_at        = run.created_at        if run else version.created_at,
        ))

    return ExperimentList(experiments=results, total=total, page=page, size=size)


# ── Get training run for a version ────────────────────────────────────────────

@router.get(
    "/models/{model_id}/versions/{version_id}/training-run",
    response_model=TrainingRunRead,
)
def get_training_run(
    model_id: int,
    version_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_version = db.query(ModelVersion).filter(
        ModelVersion.id == version_id,
        ModelVersion.model_id == model_id,
    ).first()
    if not db_version:
        raise HTTPException(status_code=404, detail="Model version not found")

    run = db.query(TrainingRun).filter(TrainingRun.version_id == version_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="No training run logged for this version")
    return run


# ── Query experiments across all models ───────────────────────────────────────

@router.get(
    "/experiments",
    response_model=ExperimentList,
)
def list_experiments(
    # Metric filters
    min_accuracy: Optional[float] = Query(None, ge=0.0, le=1.0),
    min_f1:       Optional[float] = Query(None, ge=0.0, le=1.0),
    max_loss:     Optional[float] = None,
    # Stage filter
    stage:        Optional[str]   = None,
    # Framework filter
    framework:    Optional[str]   = None,
    # Dataset filter
    dataset_name: Optional[str]   = None,
    # Sort
    sort_by:      Optional[str]   = Query("accuracy", pattern="^(accuracy|f1_score|loss|created_at)$"),
    order:        Optional[str]   = Query("desc", pattern="^(asc|desc)$"),
    # Pagination
    page:         int             = Query(1, ge=1),
    size:         int             = Query(50, ge=1, le=200),
    db:           Session         = Depends(get_db),
    current_user: User            = Depends(get_current_user),
):
    """
    Query training runs across ALL models.

    Examples:
      GET /experiments?min_accuracy=0.90
      GET /experiments?stage=prod&sort_by=f1_score&order=desc
      GET /experiments?framework=pytorch&min_f1=0.85
      GET /experiments?dataset_name=invoices-q1-2026
    """
    query = (
        db.query(ModelVersion, TrainingRun, Model)
        .join(TrainingRun, TrainingRun.version_id == ModelVersion.id)
        .join(Model, Model.id == ModelVersion.model_id)
    )

    if min_accuracy is not None:
        query = query.filter(TrainingRun.accuracy >= min_accuracy)
    if min_f1 is not None:
        query = query.filter(TrainingRun.f1_score >= min_f1)
    if max_loss is not None:
        query = query.filter(TrainingRun.loss <= max_loss)
    if stage:
        query = query.filter(ModelVersion.stage == stage)
    if framework:
        query = query.filter(TrainingRun.framework == framework)
    if dataset_name:
        query = query.filter(TrainingRun.dataset_name.contains(dataset_name))

    sort_col = {
        "accuracy":   TrainingRun.accuracy,
        "f1_score":   TrainingRun.f1_score,
        "loss":       TrainingRun.loss,
        "created_at": TrainingRun.created_at,
    }.get(sort_by, TrainingRun.accuracy)

    if order == "desc":
        query = query.order_by(sort_col.desc().nullslast())
    else:
        query = query.order_by(sort_col.asc().nullsfirst())

    total = query.count()
    rows  = query.offset((page - 1) * size).limit(size).all()

    results = [
        ExperimentSummary(
            version_id        = version.id,
            version           = version.version,
            stage             = version.stage,
            model_id          = model.id,
            model_name        = model.name,
            accuracy          = run.accuracy,
            f1_score          = run.f1_score,
            loss              = run.loss,
            learning_rate     = run.learning_rate,
            epochs            = run.epochs,
            batch_size        = run.batch_size,
            dataset_name      = run.dataset_name,
            framework         = run.framework,
            training_duration = run.training_duration,
            created_by        = run.created_by,
            created_at        = run.created_at,
        )
        for version, run, model in rows
    ]

    return ExperimentList(experiments=results, total=total, page=page, size=size)
