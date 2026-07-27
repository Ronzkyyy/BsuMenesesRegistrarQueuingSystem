"""
Rate limiter shared across API routes - backed by Redis so limits are
enforced correctly across multiple backend worker processes, not just
in a single process's memory.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from .config import settings

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    default_limits=["100/minute"],
)
