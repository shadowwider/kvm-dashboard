from __future__ import annotations

import re
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User


_SECRET_KEY_PARTS = {
    "authorization",
    "community",
    "credential",
    "jwt",
    "password",
    "privkey",
    "priv_key",
    "privacy",
    "secret",
    "token",
    "authkey",
    "auth_key",
}
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")


def _sensitive_key(key: object) -> bool:
    normalized = str(key).casefold().replace("-", "_")
    compact = normalized.replace("_", "")
    return any(
        part in normalized or part.replace("_", "") in compact
        for part in _SECRET_KEY_PARTS
    )


def redact_secrets(value: Any, *, parent_key: object | None = None) -> Any:
    """Recursively remove credentials before audit persistence or logging."""
    if parent_key is not None and _sensitive_key(parent_key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {
            str(key): redact_secrets(item, parent_key=key)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_secrets(item) for item in value]
    if isinstance(value, str):
        return _BEARER_RE.sub("Bearer [REDACTED]", value)
    return value


def request_metadata(request: Request | None) -> dict[str, str | None]:
    if request is None:
        return {
            "request_id": None,
            "ip_address": None,
            "user_agent": None,
        }
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    return {
        "request_id": request_id[:64],
        "ip_address": request.client.host[:64] if request.client else None,
        "user_agent": request.headers.get("user-agent", "")[:512] or None,
    }


def add_audit_log(
    db: AsyncSession,
    *,
    action: str,
    actor: User | None = None,
    actor_id: int | None = None,
    actor_username: str | None = None,
    actor_role: str | None = None,
    target_type: str | None = None,
    target_id: object | None = None,
    result: str = "success",
    request: Request | None = None,
    change_summary: Any = None,
) -> AuditLog:
    metadata = request_metadata(request)
    entry = AuditLog(
        actor_id=actor.id if actor is not None else actor_id,
        actor_username=actor.username if actor is not None else actor_username,
        actor_role=actor.role if actor is not None else actor_role,
        action=action,
        target_type=target_type,
        target_id=str(target_id)[:128] if target_id is not None else None,
        result=result,
        request_id=metadata["request_id"],
        ip_address=metadata["ip_address"],
        user_agent=metadata["user_agent"],
        change_summary=(
            redact_secrets(change_summary) if change_summary is not None else None
        ),
    )
    db.add(entry)
    return entry
