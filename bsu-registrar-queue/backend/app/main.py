"""
BSU Registrar Queue System - Main Application
"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .core.config import settings
from .api import router

app = FastAPI(
    title="BSU Registrar Queue System",
    description="Queue management for Bulacan State University Meneses Campus Registrar",
    version="1.0.0",
    # The frontend calls collection endpoints without a trailing slash (e.g. /api/queues).
    # Starlette's default trailing-slash redirect breaks on preflighted cross-origin
    # requests (browsers refuse to follow a redirect after a CORS preflight), so routes
    # are defined to match the no-trailing-slash path exactly instead of redirecting.
    redirect_slashes=False,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

# Serves uploaded media (backend/uploads/media/<file>) at /api/uploads/media/<file> -
# mounted under /api specifically so the frontend dev proxy (which only forwards /api/*)
# and any production reverse-proxy rule for /api reach it with no extra configuration.
UPLOADS_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/api/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")


@app.get("/")
def root():
    return {"message": "BSU Registrar Queue System API", "status": "running"}