"""
PATHS Backend — OpenTelemetry + Prometheus observability bootstrap.

PATHS-177 (Phase 8 — Launch Hardening)

Usage
-----
Call ``configure_telemetry(app, settings)`` once in ``main.py`` at
module-construction time — BEFORE the app starts serving requests.
Prometheus instrumentation adds an ASGI middleware, and Starlette forbids
adding middleware once the application lifespan has started.  Everything is
opt-in via env-vars:

    PROMETHEUS_ENABLED=true        # default true — /metrics endpoint
    OTEL_ENABLED=true              # default false — requires otel_endpoint
    OTEL_ENDPOINT=http://...       # gRPC OTLP collector (e.g. Jaeger / Honeycomb)
    OTEL_SERVICE_NAME=paths-backend
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def configure_prometheus(app) -> None:  # type: ignore[type-arg]
    """Mount a Prometheus /metrics endpoint on *app*."""
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
            should_respect_env_var=False,
            should_instrument_requests_inprogress=True,
            excluded_handlers=["/metrics", "/health", "/health/databases"],
            inprogress_labels=True,
        ).instrument(app).expose(app, include_in_schema=False)
        logger.info("Prometheus /metrics endpoint registered")
    except ImportError:
        logger.warning(
            "prometheus-fastapi-instrumentator not installed — "
            "Prometheus metrics disabled"
        )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to configure Prometheus instrumentation")


def configure_otel(service_name: str, endpoint: str) -> None:
    """
    Wire up OpenTelemetry SDK with an OTLP gRPC exporter.

    Instruments FastAPI (HTTP spans) and SQLAlchemy (DB spans).
    """
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        # Auto-instrument FastAPI (must be called before app routes are hit)
        FastAPIInstrumentor().instrument()
        # Auto-instrument SQLAlchemy — captures query durations
        SQLAlchemyInstrumentor().instrument(enable_commenter=True)

        logger.info(
            "OpenTelemetry enabled — service=%s endpoint=%s",
            service_name,
            endpoint,
        )
    except ImportError:
        logger.warning(
            "OpenTelemetry packages not installed — tracing disabled"
        )
    except Exception:  # noqa: BLE001
        logger.exception("Failed to configure OpenTelemetry")


def configure_telemetry(app, settings) -> None:  # type: ignore[type-arg]
    """
    Top-level entry point — called from ``main.py`` at module-construction
    time, before the app starts handling requests.

    Wires Prometheus and (optionally) OpenTelemetry based on ``settings``.
    """
    if settings.prometheus_enabled:
        configure_prometheus(app)

    if settings.otel_enabled and settings.otel_endpoint:
        configure_otel(settings.otel_service_name, settings.otel_endpoint)
    elif settings.otel_enabled:
        logger.warning(
            "OTel enabled but OTEL_ENDPOINT is not set — tracing skipped"
        )
