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
from .core.audit import configure_security_logging, log_security_event
from .core.config import settings
from .core.limiter import limiter
from .api import router

configure_security_logging()


def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    # slowapi's built-in handler responds with {"error": ...}, but every other
    # error path in this API (HTTPException) responds with {"detail": ...} and
    # the frontend only ever reads err.response.data.detail - matching that
    # shape here is what makes a 429 show a real message instead of the
    # generic "check your credentials" fallback.
    log_security_event(
        "security.rate_limited", outcome="blocked", request=request,
        actor="anonymous", detail=str(exc.limit.limit) if exc.limit else None,
    )
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

_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    # Hardening headers for every API/static response. The browser-facing SPA
    # gets its own (broader) header set from nginx in front of the frontend;
    # these cover the API surface and anything that reaches the backend directly.
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-site"
    # Don't advertise the server stack.
    response.headers["Server"] = "api"

    # API responses render no HTML and load no subresources, so lock the CSP
    # all the way down. Swagger/ReDoc (DEBUG only) pull assets from a CDN, so
    # they're exempted.
    if not request.url.path.startswith(_DOCS_PATHS):
        csp = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        if not settings.DEBUG:
            csp += "; upgrade-insecure-requests"
        response.headers["Content-Security-Policy"] = csp

    # HSTS: prod only (DEBUG=False) - local dev runs over plain http://localhost.
    if not settings.DEBUG:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
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