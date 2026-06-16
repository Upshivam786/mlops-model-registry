from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer
from app.routers import models, auth
from app.routers import audit                  # ← Phase 2
import os
from sqlalchemy import create_engine

security = HTTPBearer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/modelregistry")
    engine = create_engine(DATABASE_URL)
    app.state.engine = engine
    yield
    engine.dispose()

app = FastAPI(
    title="Model Registry API",
    description="MLOps Model Registry for storing, versioning, and managing machine learning models",
    version="0.2.0",                           # ← bumped to 0.2.0 for Phase 2
    lifespan=lifespan,
    redirect_slashes=False,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(models.router)
app.include_router(auth.router)
app.include_router(audit.router)               # ← Phase 2

@app.get("/")
def read_root():
    return {"message": "Model Registry API is running"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}
