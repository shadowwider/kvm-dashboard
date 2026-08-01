from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.services.audit import (
    REDACTED,
    add_audit_log,
    record_audit_log,
    redact_secrets,
)


class FakeSession:
    def __init__(self):
        self.added = []
        self.flushed = False
        self.committed = False
        self.refreshed = None

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flushed = True

    async def commit(self):
        self.committed = True

    async def refresh(self, value):
        self.refreshed = value


def make_request() -> Request:
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/api/v1/devices",
        "query_string": b"",
        "headers": [
            (b"x-request-id", b"req-audit-1"),
            (b"user-agent", b"pytest-agent"),
        ],
        "client": ("203.0.113.7", 43210),
        "server": ("testserver", 80),
        "scheme": "http",
    })


def test_redact_secrets_is_recursive_and_catches_inline_credentials():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiJ9.abcdefghijk"
    source = {
        "password": "password-value",
        "discovery": {
            "communityString": "private",
            "snmp_auth_key": "auth-value",
            "safe": "visible",
        },
        "items": [
            {"access_token": "token-value"},
            f"Bearer bearer-value {jwt}",
            "community=private token:abc123 ordinary=value",
        ],
    }

    sanitized = redact_secrets(source)

    assert sanitized["password"] == REDACTED
    assert sanitized["discovery"]["communityString"] == REDACTED
    assert sanitized["discovery"]["snmp_auth_key"] == REDACTED
    assert sanitized["discovery"]["safe"] == "visible"
    assert sanitized["items"][0]["access_token"] == REDACTED
    assert "bearer-value" not in sanitized["items"][1]
    assert jwt not in sanitized["items"][1]
    assert "private" not in sanitized["items"][2]
    assert "abc123" not in sanitized["items"][2]
    assert "ordinary=value" in sanitized["items"][2]


def test_add_audit_log_captures_actor_request_target_and_redacts_summary():
    db = FakeSession()
    actor = SimpleNamespace(id=7, username="admin", role="admin")

    entry = add_audit_log(
        db,
        actor=actor,
        action="device.update",
        target_type="device",
        target_id="CCDM-01",
        result="success",
        request=make_request(),
        change_summary={
            "before": {"community": "public", "name": "old"},
            "after": {"community": "private", "name": "new"},
        },
    )

    assert db.added == [entry]
    assert entry.actor_id == 7
    assert entry.actor_username == "admin"
    assert entry.actor_role == "admin"
    assert entry.action == "device.update"
    assert entry.target_type == "device"
    assert entry.target_id == "CCDM-01"
    assert entry.request_id == "req-audit-1"
    assert entry.ip_address == "203.0.113.7"
    assert entry.user_agent == "pytest-agent"
    assert entry.change_summary == {
        "before": {"community": REDACTED, "name": "old"},
        "after": {"community": REDACTED, "name": "new"},
    }


@pytest.mark.asyncio
async def test_record_audit_log_supports_current_or_independent_transaction():
    transactional_db = FakeSession()
    entry = await record_audit_log(
        transactional_db,
        action="discovery.scan",
        target_type="discovery_job",
        target_id=42,
    )
    assert transactional_db.added == [entry]
    assert transactional_db.flushed is True
    assert transactional_db.committed is False

    independent_db = FakeSession()
    committed_entry = await record_audit_log(
        independent_db,
        action="auth.login",
        actor_username="admin",
        commit=True,
    )
    assert independent_db.committed is True
    assert independent_db.refreshed is committed_entry
    assert independent_db.flushed is False


def test_add_audit_log_rejects_empty_action_and_result():
    db = FakeSession()
    with pytest.raises(ValueError, match="action"):
        add_audit_log(db, action=" ")
    with pytest.raises(ValueError, match="result"):
        add_audit_log(db, action="device.update", result=" ")
