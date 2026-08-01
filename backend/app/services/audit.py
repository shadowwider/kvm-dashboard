from __future__ import annotations

import re
import uuid
from collections.abc import Mapping, Sequence, Set
from datetime import date, datetime, time
from enum import Enum
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User


REDACTED = "[REDACTED]"

_SENSITIVE_KEY_MARKERS = (
    "password",
    "passwd",
    "community",
    "token",
    "secret",
    "jwt",
    "credential",
    "authorization",
    "authkey",
    "privkey",
    "privacykey",
)
_BEARER_RE = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]+")
_JWT_RE = re.compile(
    r"(?<![A-Za-z0-9_-])"
    r"[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"
    r"(?![A-Za-z0-9_-])"
)
_INLINE_SECRET_RE = re.compile(
    r"(?i)\b("
    r"password|passwd|community|token|secret|jwt|authorization|"
    r"snmp[_-]?(?:auth|priv|privacy)[_-]?(?:key|secret)"
    r")\s*([:=])\s*([^\s,;&]+)"
)


def _is_sensitive_key(key: object) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "", str(key).casefold())
    return any(marker in normalized for marker in _SENSITIVE_KEY_MARKERS)


def _redact_string(value: str) -> str:
    value = _BEARER_RE.sub("Bearer [REDACTED]", value)
    value = _JWT_RE.sub(REDACTED, value)
    return _INLINE_SECRET_RE.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{REDACTED}",
        value,
    )


def redact_secrets(value: Any, *, parent_key: object | None = None) -> Any:
    """Return a JSON-compatible copy with credentials recursively redacted."""
    if parent_key is not None and _is_sensitive_key(parent_key):
        return REDACTED
    if isinstance(value, Mapping):
        return {
            str(key): redact_secrets(item, parent_key=key)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [redact_secrets(item) for item in value]
    if isinstance(value, Set):
        return [redact_secrets(item) for item in sorted(value, key=repr)]
    if isinstance(value, str):
        return _redact_string(value)
    if isinstance(value, Enum):
        return redact_secrets(value.value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return REDACTED
    return value


def request_metadata(
    request: Request | None,
    *,
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> dict[str, str | None]:
    """Resolve bounded request metadata, allowing background-job overrides."""
    if request is not None:
        request_id = request_id or request.headers.get("x-request-id") or str(uuid.uuid4())
        ip_address = ip_address or (request.client.host if request.client else None)
        user_agent = user_agent or request.headers.get("user-agent")

    return {
        "request_id": request_id[:64] if request_id else None,
        "ip_address": ip_address[:64] if ip_address else None,
        "user_agent": _redact_string(user_agent[:512]) if user_agent else None,
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
    request_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    change_summary: Any = None,
) -> AuditLog:
    """Add a sanitized audit row to the caller's current transaction."""
    action = action.strip()
    result = result.strip()
    if not action:
        raise ValueError("action must not be empty")
    if not result:
        raise ValueError("result must not be empty")

    metadata = request_metadata(
        request,
        request_id=request_id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    entry = AuditLog(
        actor_id=actor.id if actor is not None else actor_id,
        actor_username=(
            actor.username if actor is not None else actor_username
        ),
        actor_role=actor.role if actor is not None else actor_role,
        action=action[:128],
        target_type=target_type[:64] if target_type else None,
        target_id=str(target_id)[:128] if target_id is not None else None,
        result=result[:16],
        request_id=metadata["request_id"],
        ip_address=metadata["ip_address"],
        user_agent=metadata["user_agent"],
        change_summary=(
            redact_secrets(change_summary) if change_summary is not None else None
        ),
    )
    db.add(entry)
    return entry


async def record_audit_log(
    db: AsyncSession,
    *,
    commit: bool = False,
    flush: bool = True,
    **fields: Any,
) -> AuditLog:
    """Add an audit row and optionally persist it as an independent transaction."""
    entry = add_audit_log(db, **fields)
    if commit:
        await db.commit()
        await db.refresh(entry)
    elif flush:
        await db.flush()
    return entry


__all__ = [
    "REDACTED",
    "add_audit_log",
    "record_audit_log",
    "redact_secrets",
    "request_metadata",
]
