from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Model(Base):
    __tablename__ = "models"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    owner       = Column(String(255), nullable=True)
    tags        = Column(String(500), nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    versions = relationship("ModelVersion", back_populates="model", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Model(id={self.id}, name='{self.name}')>"


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id          = Column(Integer, primary_key=True, index=True)
    model_id    = Column(Integer, ForeignKey("models.id"), nullable=False)
    version     = Column(String(50), nullable=False)
    stage       = Column(String(50), default="dev", nullable=False)
    description = Column(Text, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    model        = relationship("Model", back_populates="versions")
    artifacts    = relationship("ModelArtifact", back_populates="version", cascade="all, delete-orphan")
    training_run = relationship("TrainingRun", back_populates="version", uselist=False, cascade="all, delete-orphan")

    # ← Phase 5B: one model card per version
    model_card   = relationship("ModelCard", back_populates="version", uselist=False, cascade="all, delete-orphan")
    # ← Phase 5C: many dataset links per version
    dataset_links = relationship("DatasetLink", back_populates="version", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ModelVersion(id={self.id}, model_id={self.model_id}, version='{self.version}')>"


class ModelArtifact(Base):
    __tablename__ = "model_artifacts"

    id            = Column(Integer, primary_key=True, index=True)
    version_id    = Column(Integer, ForeignKey("model_versions.id"), nullable=False)
    artifact_type = Column(String(100), nullable=False)
    artifact_path = Column(String(500), nullable=False)
    file_size     = Column(Integer, nullable=True)
    checksum      = Column(String(255), nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow, nullable=False)

    version = relationship("ModelVersion", back_populates="artifacts")

    def __repr__(self):
        return f"<ModelArtifact(id={self.id}, version_id={self.version_id}, type='{self.artifact_type}')>"


class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String(100), unique=True, nullable=False, index=True)
    email           = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role            = Column(String(50), default="viewer", nullable=False)
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=datetime.utcnow, nullable=False)

    audit_logs = relationship("AuditLog", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False)
    username      = Column(String(100), nullable=False)
    action        = Column(String(50),  nullable=False)
    resource_type = Column(String(50),  nullable=False)
    resource_id   = Column(Integer,     nullable=False)
    old_value     = Column(Text,        nullable=True)
    new_value     = Column(Text,        nullable=True)
    timestamp     = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action}', resource='{self.resource_type}:{self.resource_id}')>"


class TrainingRun(Base):
    """
    One training run per model version.
    Stores hyperparameters, metrics, and dataset info as queryable fields.

    hyperparameters : JSON string  {"lr": 0.001, "epochs": 50, "batch_size": 32}
    metrics         : JSON string  {"accuracy": 0.94, "f1": 0.91, "loss": 0.12}

    Top-level metric columns (accuracy, f1, loss) are stored separately
    so they can be filtered and sorted without parsing JSON in SQL.
    """
    __tablename__ = "training_runs"

    id                  = Column(Integer, primary_key=True, index=True)
    version_id          = Column(Integer, ForeignKey("model_versions.id"), nullable=False, unique=True)

    # Dataset
    dataset_name        = Column(String(255), nullable=True)
    dataset_hash        = Column(String(255), nullable=True)   # SHA256 of training data

    # Hyperparameters — full JSON for storage, key ones as columns for querying
    hyperparameters     = Column(Text, nullable=True)          # full JSON string
    learning_rate       = Column(Float, nullable=True)
    epochs              = Column(Integer, nullable=True)
    batch_size          = Column(Integer, nullable=True)

    # Metrics — full JSON for storage, key ones as columns for querying
    metrics             = Column(Text, nullable=True)          # full JSON string
    accuracy            = Column(Float, nullable=True, index=True)
    f1_score            = Column(Float, nullable=True, index=True)
    loss                = Column(Float, nullable=True)

    # Framework
    framework           = Column(String(100), nullable=True)   # pytorch | sklearn | tensorflow
    framework_version   = Column(String(50),  nullable=True)

    # Duration in seconds
    training_duration   = Column(Integer, nullable=True)

    # Who logged this run
    created_by          = Column(String(100), nullable=False)
    created_at          = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    version = relationship("ModelVersion", back_populates="training_run")

    def __repr__(self):
        return f"<TrainingRun(id={self.id}, version_id={self.version_id}, accuracy={self.accuracy})>"


# ── Phase 5B — Model Cards ───────────────────────────────────────────────────

class ModelCard(Base):
    """
    Structured governance documentation for a single model version.
    One card per version (1:1, like TrainingRun) — covers intended use,
    limitations, ethical considerations, and evaluation context that
    don't belong as raw metrics but matter for responsible deployment.
    """
    __tablename__ = "model_cards"

    id                      = Column(Integer, primary_key=True, index=True)
    version_id              = Column(Integer, ForeignKey("model_versions.id"), nullable=False, unique=True)

    intended_use            = Column(Text, nullable=True)
    limitations             = Column(Text, nullable=True)
    ethical_considerations  = Column(Text, nullable=True)
    training_data_summary   = Column(Text, nullable=True)
    evaluation_summary      = Column(Text, nullable=True)
    caveats_and_recommendations = Column(Text, nullable=True)

    created_by              = Column(String(100), nullable=False)
    created_at              = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at              = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    version = relationship("ModelVersion", back_populates="model_card")

    def __repr__(self):
        return f"<ModelCard(id={self.id}, version_id={self.version_id})>"


# ── Phase 5C — Data Lineage ──────────────────────────────────────────────────

class DatasetLink(Base):
    """
    Links a training dataset to a model version. Many-to-one from the
    dataset's perspective (one dataset can train many versions), and
    one-to-many from the version's perspective (a version could in
    principle cite more than one dataset, e.g. pretrain + finetune sets).

    dataset_hash is the primary identity of a dataset for lineage purposes —
    two links with the same hash refer to the same physical dataset even if
    dataset_name differs across teams/runs.
    """
    __tablename__ = "dataset_links"

    id            = Column(Integer, primary_key=True, index=True)
    version_id    = Column(Integer, ForeignKey("model_versions.id"), nullable=False, index=True)

    dataset_name  = Column(String(255), nullable=False)
    dataset_hash  = Column(String(255), nullable=False, index=True)
    dataset_uri   = Column(String(500), nullable=True)   # e.g. gs://bucket/path or local path
    role          = Column(String(50), default="training", nullable=False)  # training | validation | test
    row_count     = Column(Integer, nullable=True)
    notes         = Column(Text, nullable=True)

    linked_by     = Column(String(100), nullable=False)
    created_at    = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    version = relationship("ModelVersion", back_populates="dataset_links")

    def __repr__(self):
        return f"<DatasetLink(id={self.id}, version_id={self.version_id}, dataset_hash='{self.dataset_hash}')>"
