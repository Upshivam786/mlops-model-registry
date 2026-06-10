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
    tags = Column(String(500), nullable=True)  # Comma-separated tags
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    versions = relationship("ModelVersion", back_populates="model", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Model(id={self.id}, name='{self.name}')>"

class ModelVersion(Base):
    __tablename__ = "model_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    model_id = Column(Integer, ForeignKey("models.id"), nullable=False)
    version = Column(String(50), nullable=False)  # Could be semantic version or custom
    stage = Column(String(50), default="dev", nullable=False)  # dev, staging, prod, archived
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    model = relationship("Model", back_populates="versions")
    artifacts = relationship("ModelArtifact", back_populates="version", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ModelVersion(id={self.id}, model_id={self.model_id}, version='{self.version}')>"

class ModelArtifact(Base):
    __tablename__ = "model_artifacts"
    
    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, ForeignKey("model_versions.id"), nullable=False)
    artifact_type = Column(String(100), nullable=False)  # weights, config, metrics, etc.
    artifact_path = Column(String(500), nullable=False)  # Path in storage
    file_size = Column(Integer, nullable=True)  # Size in bytes
    checksum = Column(String(255), nullable=True)  # SHA256 or similar
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
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

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"
