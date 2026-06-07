"""JSON structured logging, OpenTelemetry log-data-model compatible.

Emits one JSON object per line with the field names recommended in the
server AGENT.md (timestamp, severity_text, severity_number, service_name,
trace_id, span_id, event_name, message, attributes, ...). Reserved fields
listed in NEVER_LOG must never be emitted.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

# OTel SeverityNumber mapping (subset).
_SEVERITY_NUMBER = {
    "DEBUG": 5,
    "INFO": 9,
    "WARNING": 13,
    "WARN": 13,
    "ERROR": 17,
    "CRITICAL": 21,
}

_STANDARD_FIELDS = {
    "service_name",
    "service_version",
    "deployment_environment",
    "trace_id",
    "span_id",
    "session_id",
    "user_id",
    "device_id",
    "interaction_id",
    "event_name",
}

NEVER_LOG = {"password", "token", "api_key", "authorization", "audio"}


class JsonFormatter(logging.Formatter):
    def __init__(self, service_name: str, service_version: str, environment: str) -> None:
        super().__init__()
        self._service_name = service_name
        self._service_version = service_version
        self._environment = environment

    def format(self, record: logging.LogRecord) -> str:
        severity_text = record.levelname
        timestamp = (
            datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z")
        )
        payload: dict[str, Any] = {
            "timestamp": timestamp,
            "severity_text": severity_text,
            "severity_number": _SEVERITY_NUMBER.get(severity_text, 0),
            "service_name": self._service_name,
            "service_version": self._service_version,
            "deployment_environment": self._environment,
            "message": record.getMessage(),
        }

        for field in _STANDARD_FIELDS:
            value = getattr(record, field, None)
            if value is not None and field not in payload:
                payload[field] = value

        attributes = getattr(record, "attributes", None)
        if isinstance(attributes, dict):
            payload["attributes"] = {
                k: v for k, v in attributes.items() if k.lower() not in NEVER_LOG
            }

        if record.exc_info:
            payload["attributes"] = payload.get("attributes", {})
            payload["attributes"]["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def configure_logging(
    *,
    service_name: str,
    service_version: str,
    environment: str,
    level: str = "INFO",
) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        JsonFormatter(
            service_name=service_name,
            service_version=service_version,
            environment=environment,
        )
    )
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
