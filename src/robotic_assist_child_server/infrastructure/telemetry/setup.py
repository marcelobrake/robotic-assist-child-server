"""Telemetry bootstrap.

Always configures OpenTelemetry-compatible JSON logging. OpenTelemetry SDK
tracing is initialized best-effort: if the SDK is unavailable it degrades to
logging only, so the MVP slice runs without an OTel collector.
"""
from __future__ import annotations

from ...config.settings import Settings
from ...shared.logging import configure_logging, get_logger


def init_telemetry(settings: Settings) -> bool:
    configure_logging(
        service_name=settings.service_name,
        service_version=settings.service_version,
        environment=settings.deployment_environment,
        level=settings.log_level,
    )
    logger = get_logger(__name__)

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider

        resource = Resource.create(
            {
                "service.name": settings.service_name,
                "service.version": settings.service_version,
                "deployment.environment": settings.deployment_environment,
            }
        )
        trace.set_tracer_provider(TracerProvider(resource=resource))
        logger.info(
            "telemetry initialized",
            extra={"event_name": "telemetry.init", "attributes": {"tracing": True}},
        )
    except Exception:  # pragma: no cover - optional dependency / env
        logger.info(
            "telemetry initialized (logging only)",
            extra={"event_name": "telemetry.init", "attributes": {"tracing": False}},
        )

    return True
