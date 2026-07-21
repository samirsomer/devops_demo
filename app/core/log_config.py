from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings


# holds the current request correlation id for the lifetime of the request.
req_id_ctx_var: ContextVar[str | None] = ContextVar("request_id", default=None)


class JSONFormatter(logging.Formatter):
    """Renders log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": req_id_ctx_var.get(),
        }

        # Attach any extra fields passed via logger.info(..., extra={...})
        reserved = logging.LogRecord(
            "", 0, "", 0, "", (), None
        ).__dict__.keys()
        for key, value in record.__dict__.items():
            if key not in reserved and key not in payload:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)



class TextFormatter(logging.Formatter):
    """Human-friendly formatter for local development."""

    def format(self, record: logging.LogRecord) -> str:
        request_id = req_id_ctx_var.get() or "-"
        base = (
            f"{self.formatTime(record)} | {record.levelname:<8} | "
            f"req={request_id} | {record.name} | {record.getMessage()}"
        )
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def configure_logging() -> None:
    """Configure the root logger according to application settings.

    Should be called once, at application startup.
    """
    settings = get_settings()

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JSONFormatter() if settings.log_json else TextFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(settings.log_level.upper())

    # Keep noisy third-party loggers reasonable.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
