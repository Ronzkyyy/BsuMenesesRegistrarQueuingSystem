"""
BSU Registrar Queue System - Main Application
"""
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from .core.config import settings
from .core.limiter import limiter
from .api import router


def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    # slowapi's built-in handler responds with {"error": ...}, but every other
    # error path in this API (HTTPException) responds with {"detail": ...} and
    # the frontend only ever reads err.response.data.detail - matching that
    # shape here is what makes a 429 show a real message instead of the
    # generic "check your credentials" fallback.
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many attempts. Please wait a moment and try again."},
    )

app = FastAPI(
    title="BSU Registrar Queue System",
    description="Queue management for Bulacan State University Meneses Campus Registrar",
    version="1.0.0",
    # The frontend calls collection endpoints without a trailing slash (e.g. /api/queues).
    # Starlette's default trailing-slash redirect breaks on preflighted cross-origin
    # requests (browsers refuse to follow a redirect after a CORS preflight), so routes
    # are defined to match the no-trailing-slash path exactly instead of redirecting.
    redirect_slashes=False,
    # Interactive docs/schema reveal the full API surface - keep them out of prod.
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    # Cheap, universally-safe hardening headers - none of these constrain
    # anything this app actually does (no iframes, no cross-origin embeds),
    # so there's no compatibility risk. A reverse proxy in front of this in
    # production may also set these; duplicates are harmless.
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # HTTPS-everywhere headers, prod only (DEBUG=False). Skipped in local dev
    # because it runs over plain http://localhost. HSTS tells browsers to
    # never speak HTTP to this host again; upgrade-insecure-requests makes
    # them rewrite any stray http:// subresource (e.g. a link-type media
    # item) to https:// instead of blocking it as mixed content.
    if not settings.DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "upgrade-insecure-requests"
    return response


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
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