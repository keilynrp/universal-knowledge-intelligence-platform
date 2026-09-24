import json
import logging
import os
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from backend.principal import principal_of

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

# Fields copied from a record's `extra` into the formatted line, when present.
# The identity fields (#376) come from the principal the auth dependency
# recorded; they are absent, never placeholders, on anonymous or refused
# requests, so a filter on user_id cannot match a line that had no identity.
_RECORD_FIELDS = (
    "event", "method", "path", "status_code", "duration_ms", "client_ip",
    "user_id", "session_id", "api_key_id",
)


def current_log_format() -> str:
    return os.environ.get("LOG_FORMAT", "json").lower()


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = getattr(record, "request_id", request_id_ctx.get())
        return True


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", request_id_ctx.get()),
        }

        for field in _RECORD_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        if current_log_format() == "text":
            parts = [
                f"ts={payload['timestamp']}",
                f"level={payload['level']}",
                f"logger={payload['logger']}",
                f"request_id={payload['request_id']}",
            ]
            for field in _RECORD_FIELDS:
                if field in payload:
                    parts.append(f"{field}={payload[field]}")
            parts.append(f"message={payload['message']}")
            if "exception" in payload:
                parts.append(f"exception={payload['exception']}")
            return " ".join(parts)

        return json.dumps(payload, ensure_ascii=True)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    handler.addFilter(RequestContextFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())


def _identity(request: Request) -> dict[str, int | str]:
    """Who the request acted as, for the log line; empty when nobody was accepted."""
    principal = principal_of(request)
    return principal.log_fields() if principal else {}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx.set(request_id)
        request.state.request_id = request_id
        start = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logging.getLogger("ukip.request").exception(
                "request_failed",
                extra={
                    "event": "request_failed",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": 500,
                    "duration_ms": duration_ms,
                    "client_ip": request.client.host if request.client else None,
                    "request_id": request_id,
                    **_identity(request),
                },
            )
            request_id_ctx.reset(token)
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        logging.getLogger("ukip.request").info(
            "request_completed",
            extra={
                "event": "request_completed",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": request.client.host if request.client else None,
                "request_id": request_id,
                **_identity(request),
            },
        )
        request_id_ctx.reset(token)
        return response
