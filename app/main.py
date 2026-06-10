from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import models
import os
from sqlalchemy import create_engine
from app.routers import auth

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create the database engine
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/modelregistry")
    engine = create_engine(DATABASE_URL)
    app.state.engine = engine
    yield
    # Dispose the engine on shutdown
    engine.dispose()

app = FastAPI(
    title="Model Registry API",
    description="MLOps Model Registry for storing, versioning, and managing machine learning models",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(models.router)

@app.get("/")
def read_root():
    return {"message": "Model Registry API is running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

app.include_router(auth.router)


