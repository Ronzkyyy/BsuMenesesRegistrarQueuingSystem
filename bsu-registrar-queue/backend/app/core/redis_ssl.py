"""
TLS settings for Celery when REDIS_URL uses rediss:// (hosted Redis).

Celery's Redis result backend refuses to start on a rediss:// URL that
doesn't say how to verify the server certificate ("A rediss:// URL must have
parameter ssl_cert_reqs ..."), and the broker silently falls back to *no*
verification. Production's REDIS_URL had no such parameter, so the inline
worker crashed on every boot and no background task ever ran. Default to full
certificate verification instead of relying on the URL being hand-edited.
"""
import ssl
from urllib.parse import parse_qs, urlparse


def redis_ssl_options(url: str) -> dict:
    """SSL options for a rediss:// URL, or {} for plain redis:// or when the
    URL already sets ssl_cert_reqs itself (an explicit choice wins)."""
    parsed = urlparse(url)
    if parsed.scheme != "rediss":
        return {}
    if "ssl_cert_reqs" in parse_qs(parsed.query):
        return {}
    return {"ssl_cert_reqs": ssl.CERT_REQUIRED}


def configure_redis_ssl(celery_app, url: str) -> None:
    """Apply redis_ssl_options to both the broker and the result backend."""
    options = redis_ssl_options(url)
    if options:
        celery_app.conf.broker_use_ssl = options
        celery_app.conf.redis_backend_use_ssl = options
