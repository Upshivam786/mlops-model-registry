from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Model(Base):
    __tablename__ = "models"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    owner = Column(String(255), nullable=True)
    tags = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    versions = relationship("ModelVersion", back_populates="model", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Model(id={self.id}, name='{self.name}')>"


class ModelVersion(Base):
    __tablename__ = "model_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("models.id"), nullable=False)
    version = Column(String(50), nullable=False)
    stage = Column(String(50), default="dev", nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    model = relationship("Model", back_populates="versions")
    artifacts = relationship("ModelArtifact", back_populates="version", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ModelVersion(id={self.id}, model_id={self.model_id}, version='{self.version}')>"


class ModelArtifact(Base):
    __tablename__ = "model_artifacts"
    
    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, ForeignKey("model_versions.id"), nullable=False)
    artifact_type = Column(String(100), nullable=False)
    artifact_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=True)
    checksum = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    version = relationship("ModelVersion", back_populates="artifacts")
    
    def __repr__(self):
        return f"<ModelArtifact(id={self.id}, version_id={self.version_id}, type='{self.artifact_type}')>"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), default="viewer", nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    audit_logs = relationship("AuditLog", back_populates="user")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"


class AuditLog(Base):
    """
    Immutable record of every write action in the system.

    action        : CREATE | UPDATE | DELETE | PROMOTE
    resource_type : model | model_version | artifact
    resource_id   : the integer PK of the affected row
    old_value     : JSON string of state before the change (nullable)
    new_value     : JSON string of state after the change (nullable)
    """
    __tablename__ = "audit_logs"

    id            = Column(Integer, primary_key=True, index=True)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False)
    username      = Column(String(100), nullable=False)          # denormalised for fast reads
    action        = Column(String(50),  nullable=False)          # CREATE | UPDATE | DELETE | PROMOTE
    resource_type = Column(String(50),  nullable=False)          # model | model_version | artifact
    resource_id   = Column(Integer,     nullable=False)
    old_value     = Column(Text,        nullable=True)           # JSON string
    new_value     = Column(Text,        nullable=True)           # JSON string
    timestamp     = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action}', resource='{self.resource_type}:{self.resource_id}')>"
