"""Celery must start against a TLS Redis URL (rediss://) that doesn't spell
out ssl_cert_reqs - production's REDIS_URL looks like that, and the worker
crashed on every boot until configure_redis_ssl was added."""
import ssl

import pytest
from celery import Celery

from app.core.redis_ssl import configure_redis_ssl, redis_ssl_options

TLS_URL = "rediss://default:secret@redis.example.com:6379"


def test_rediss_url_defaults_to_full_certificate_verification():
    assert redis_ssl_options(TLS_URL) == {"ssl_cert_reqs": ssl.CERT_REQUIRED}


def test_plain_redis_url_gets_no_ssl_options():
    assert redis_ssl_options("redis://localhost:6379/0") == {}


def test_explicit_ssl_cert_reqs_in_url_is_left_alone():
    assert redis_ssl_options(TLS_URL + "?ssl_cert_reqs=CERT_REQUIRED") == {}


def test_result_backend_rejects_bare_rediss_url_without_the_fix():
    """Reproduces the production crash."""
    app = Celery("t", broker=TLS_URL, backend=TLS_URL)
    with pytest.raises(ValueError, match="ssl_cert_reqs"):
        app.backend


def test_result_backend_and_broker_accept_bare_rediss_url_with_the_fix():
    app = Celery("t", broker=TLS_URL, backend=TLS_URL)
    configure_redis_ssl(app, TLS_URL)

    assert app.backend.connparams["ssl_cert_reqs"] == ssl.CERT_REQUIRED
    assert app.conf.broker_use_ssl == {"ssl_cert_reqs": ssl.CERT_REQUIRED}


def test_plain_redis_app_is_unchanged():
    app = Celery("t", broker="redis://localhost:6379/0", backend="redis://localhost:6379/0")
    configure_redis_ssl(app, "redis://localhost:6379/0")

    assert not app.conf.broker_use_ssl
    assert "ssl_cert_reqs" not in app.backend.connparams
