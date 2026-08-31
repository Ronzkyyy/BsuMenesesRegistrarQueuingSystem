"""Security audit log.

One JSON object per line on the `bsu.security` logger, routed to stdout at
INFO regardless of LOG_LEVEL (see `configure_security_logging`). Never pass a
password, token, or raw request body in here.
"""
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional

from fastapi import Request

logger = logging.getLogger("bsu.security")

_configured = False


def configure_security_logging() -> None:
    """Attach a stdout handler to the security logger. Idempotent."""
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    # Security events are always recorded, even if the app log level is higher.
    logger.setLevel(logging.INFO)
    logger.propagate = False
    # Guard against a stray logging.config.*Config(disable_existing_loggers=True)
    # elsewhere in the process having switched this logger off.
    logger.disabled = False
    _configured = True


def _client_ip(request: Optional[Request]) -> Optional[str]:
    # uvicorn --proxy-headers rewrites request.client from X-Forwarded-For, so
    # this is the real caller in production, not the proxy.
    if request is not None and request.client is not None:
        return request.client.host
    return None


def log_security_event(
    event: str,
    *,
    outcome: str,
    request: Optional[Request] = None,
    actor: Optional[str] = None,
    actor_role: Optional[str] = None,
    target: Optional[str] = None,
    detail: Optional[str] = None,
    **extra: object,
) -> None:
    """Emit one security-audit record.

    event:   dotted name, e.g. "auth.login", "authz.denied", "student.deleted"
    outcome: "success" | "failure" | "denied" | "blocked"
    actor:   username performing the action, or "anonymous"
    target:  what was acted on (a username, student id, queue name, ...)
    """
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "outcome": outcome,
        "actor": actor,
        "actor_role": actor_role,
        "target": target,
        "client_ip": _client_ip(request),
        "path": request.url.path if request is not None else None,
        "detail": detail,
    }
    record.update(extra)
    record = {k: v for k, v in record.items() if v is not None}
    logger.info(json.dumps(record, default=str))
